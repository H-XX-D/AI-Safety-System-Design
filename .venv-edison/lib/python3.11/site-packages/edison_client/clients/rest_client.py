# ruff: noqa: PLR0915
import ast
import asyncio
import base64
import contextlib
import copy
import importlib.metadata
import inspect
import json
import logging
import os
import sys
import time
from collections.abc import Collection
from http import HTTPStatus
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, cast
from uuid import UUID

import cloudpickle
import httpx_aiohttp
from aviary.functional import EnvironmentBuilder
from httpx import (
    AsyncClient,
    Client,
    CloseError,
    HTTPStatusError,
    codes,
)
from ldp.agent import AgentConfig
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)
from tqdm import tqdm as sync_tqdm
from tqdm.asyncio import tqdm

from edison_client.clients.data_storage_methods import DataStorageMethods
from edison_client.models.app import (
    AuthType,
    JobDeploymentConfig,
    JobNames,
    LiteTaskResponse,
    RuntimeConfig,
    Stage,
    TaskRequest,
    TaskResponse,
    TaskResponseVerbose,
    TrajectoryQueryParams,
)
from edison_client.models.data_storage_methods import (
    PermittedAccessors,
    ShareStatus,
)
from edison_client.models.job_event import (
    JobEventBatchCreateRequest,
    JobEventBatchCreateResponse,
    JobEventCreateRequest,
    JobEventCreateResponse,
    JobEventUpdateRequest,
)
from edison_client.models.rest import (
    DiscoveryResponse,
    ExecutionStatus,
    SearchCriterion,
    UserAgentRequest,
    UserAgentRequestPostPayload,
    UserAgentRequestStatus,
    UserAgentResponsePayload,
    WorldModel,
    WorldModelResponse,
    WorldModelSearchPayload,
)
from edison_client.utils.auth import RefreshingJWT
from edison_client.utils.general import (
    create_retry_if_connection_error,
    gather_with_concurrency,
)
from edison_client.utils.module_utils import (
    OrganizationSelector,
    fetch_environment_function_docstring,
)
from edison_client.utils.monitoring import (
    external_trace,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
TaskRequest.model_rebuild()

FILE_UPLOAD_IGNORE_PARTS = {
    ".ruff_cache",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
}


class RestClientError(Exception):
    """Base exception for REST client errors."""


class TaskFetchError(RestClientError):
    """Raised when there's an error fetching a task."""


class JobFetchError(RestClientError):
    """Raised when there's an error fetching a job."""


class JobCreationError(RestClientError):
    """Raised when there's an error creating a job."""


class UserAgentRequestError(RestClientError):
    """Base exception for User Agent Request operations."""


class UserAgentRequestFetchError(UserAgentRequestError):
    """Raised when there's an error fetching a user agent request."""


class UserAgentRequestCreationError(UserAgentRequestError):
    """Raised when there's an error creating a user agent request."""


class UserAgentRequestResponseError(UserAgentRequestError):
    """Raised when there's an error responding to a user agent request."""


class WorldModelFetchError(RestClientError):
    """Raised when there's an error fetching a world model."""


class WorldModelCreationError(RestClientError):
    """Raised when there's an error creating a world model."""


class WorldModelDeletionError(RestClientError):
    """Raised when there's an error deleting a world model."""


class ProjectError(RestClientError):
    """Raised when there's an error with trajectory group operations."""


class DiscoveryCreationError(RestClientError):
    """Raised when there's an error creating a discovery."""


class DiscoveryFetchError(RestClientError):
    """Raised when there's an error fetching a discovery."""


class InvalidTaskDescriptionError(Exception):
    """Raised when the task description is invalid or empty."""


class FileUploadError(RestClientError):
    """Raised when there's an error uploading a file."""


class JobEventClientError(RestClientError):
    """Raised when there's an error with job event operations."""


class JobEventCreationError(JobEventClientError):
    """Raised when there's an error creating a job event."""


class JobEventUpdateError(JobEventClientError):
    """Raised when there's an error updating a job event."""


class JobEventBatchCreationError(JobEventClientError):
    """Raised when there's an error creating job events in batch."""


retry_if_connection_error = create_retry_if_connection_error(FileUploadError)

DEFAULT_AGENT_TIMEOUT: int = 2400  # seconds


class RestClient(DataStorageMethods):  # noqa: PLR0904
    REQUEST_TIMEOUT: ClassVar[float] = 30.0  # sec - for general API calls
    FILE_UPLOAD_TIMEOUT: ClassVar[float] = 600.0  # 10 minutes - for file uploads
    MAX_RETRY_ATTEMPTS: ClassVar[int] = 3
    RETRY_MULTIPLIER: ClassVar[int] = 1
    MAX_RETRY_WAIT: ClassVar[int] = 10
    DEFAULT_POLLING_TIME: ClassVar[int] = 5  # seconds
    CHUNK_SIZE: ClassVar[int] = 16 * 1024 * 1024  # 16MB chunks
    ASSEMBLY_POLLING_INTERVAL: ClassVar[int] = 10  # seconds
    MAX_ASSEMBLY_WAIT_TIME: ClassVar[int] = 1800  # 30 minutes
    MAX_CONCURRENT_CHUNKS: ClassVar[int] = 12  # Maximum concurrent chunk uploads

    def __init__(  # noqa: PLR0917
        self,
        stage: str | Stage = Stage.PROD,
        service_uri: str | None = None,
        organization: str | None = None,
        auth_type: AuthType = AuthType.API_KEY,
        api_key: str | None = None,
        jwt: str | None = None,
        headers: dict[str, str] | None = None,
        verbose_logging: bool = False,
    ):
        if verbose_logging:
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.WARNING)

        self.stage = stage if isinstance(stage, Stage) else Stage[stage.upper()]
        self.base_url = service_uri or self.stage.value
        self.auth_type = auth_type
        self.api_key = api_key or os.environ.get("EDISON_PLATFORM_API_KEY")
        self._clients: dict[str, Client | AsyncClient] = {}
        self.headers = headers or {}
        self.jwt = jwt
        self.organizations: list[str] = self._filter_orgs(organization)

    @property
    def client(self) -> Client:
        """Authenticated HTTP client for regular API calls."""
        return cast(Client, self.get_client("application/json", authenticated=True))

    @property
    def async_client(self) -> AsyncClient:
        """Authenticated async HTTP client for regular API calls."""
        return cast(
            AsyncClient,
            self.get_client("application/json", authenticated=True, async_client=True),
        )

    @property
    def unauthenticated_client(self) -> Client:
        """Unauthenticated HTTP client for auth operations."""
        return cast(Client, self.get_client("application/json", authenticated=False))

    @property
    def multipart_client(self) -> Client:
        """Authenticated HTTP client for multipart uploads."""
        return cast(Client, self.get_client(None, authenticated=True))

    @property
    def file_upload_client(self) -> Client:
        """Authenticated HTTP client with extended timeout for file uploads."""
        return cast(
            Client,
            self.get_client(
                "application/json", authenticated=True, timeout=self.FILE_UPLOAD_TIMEOUT
            ),
        )

    @property
    def async_file_upload_client(self) -> AsyncClient:
        """Authenticated async HTTP client with extended timeout for file uploads."""
        return cast(
            AsyncClient,
            self.get_client(
                "application/json",
                authenticated=True,
                async_client=True,
                timeout=self.FILE_UPLOAD_TIMEOUT,
            ),
        )

    def get_client(
        self,
        content_type: str | None = "application/json",
        authenticated: bool = True,
        async_client: bool = False,
        timeout: float | None = None,
    ) -> Client | AsyncClient:
        """Return a cached HTTP client or create one if needed.

        Args:
            content_type: The desired content type header. Use None for multipart uploads.
            authenticated: Whether the client should include authentication.
            async_client: Whether to use an async client.
            timeout: Custom timeout in seconds. Uses REQUEST_TIMEOUT if not provided.

        Returns:
            An HTTP client configured with the appropriate headers.
        """
        client_timeout = timeout or self.REQUEST_TIMEOUT
        key = f"{content_type or 'multipart'}_{authenticated}_{async_client}_{client_timeout}"

        if key not in self._clients:
            headers = copy.deepcopy(self.headers)
            auth = None

            if authenticated:
                auth = RefreshingJWT(
                    # authenticated=False will always return a synchronous client
                    auth_client=cast(
                        Client, self.get_client("application/json", authenticated=False)
                    ),
                    auth_type=self.auth_type,
                    api_key=self.api_key,
                    jwt=self.jwt,
                )

            if content_type:
                headers["Content-Type"] = content_type

            headers["x-client"] = "sdk"

            self._clients[key] = (
                httpx_aiohttp.HttpxAiohttpClient(
                    base_url=self.base_url,
                    headers=headers,
                    timeout=client_timeout,
                    auth=auth,
                )
                if async_client
                else Client(
                    base_url=self.base_url,
                    headers=headers,
                    timeout=client_timeout,
                    auth=auth,
                )
            )

        return self._clients[key]

    def close(self):
        """Explicitly close all cached clients."""
        for client in self._clients.values():
            if isinstance(client, Client):
                with contextlib.suppress(RuntimeError, CloseError):
                    client.close()

    async def aclose(self):
        """Asynchronously close all cached clients."""
        for client in self._clients.values():
            if isinstance(client, AsyncClient):
                with contextlib.suppress(RuntimeError, CloseError):
                    await client.aclose()

    def __del__(self):
        self.close()

    def _filter_orgs(self, organization: str | None = None) -> list[str]:
        filtered_orgs = [
            org
            for org in self._fetch_my_orgs()
            if (org == organization or organization is None)
        ]
        if not filtered_orgs:
            raise ValueError(f"Organization '{organization}' not found.")
        return filtered_orgs

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _check_job(self, name: str, organization: str) -> dict[str, Any]:
        response = self.client.get(f"/v0.1/crows/{name}/organizations/{organization}")
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_my_orgs(self) -> list[str]:
        response = self.client.get(f"/v0.1/organizations?filter={True}")
        response.raise_for_status()
        orgs = response.json()
        return [org["name"] for org in orgs]

    @staticmethod
    def _validate_module_path(path: Path) -> None:
        """Validates that the given path exists and is a directory.

        Args:
            path: Path to validate

        Raises:
            JobFetchError: If the path is not a directory

        """
        if not path.is_dir():
            raise JobFetchError(f"Path {path} is not a directory.")

    @staticmethod
    def _validate_template_path(template_path: str | os.PathLike) -> None:
        """
        Validates that a template path exists and is a file.

        Args:
            template_path: Path to validate

        Raises:
            FileNotFoundError: If the template path doesn't exist
            ValueError: If the path exists but isn't a file
        """
        template_path = Path(template_path)
        if not template_path.exists():
            raise FileNotFoundError(
                f"Markdown template file not found: {template_path}"
            )
        if not template_path.is_file():
            raise ValueError(
                f"Markdown template path exists but is not a file: {template_path}"
            )

    @staticmethod
    def _validate_files(files: list, path: str | os.PathLike) -> None:
        """Validates that files were found in the given path.

        Args:
            files: List of collected files
            path: Path that was searched for files

        Raises:
            TaskFetchError: If no files were found

        """
        if not files:
            raise TaskFetchError(f"No files found in {path}.")

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_task(
        self,
        task_id: str | None = None,
        history: bool = False,
        verbose: bool = False,
        lite: bool = False,
    ) -> TaskResponse | TaskResponseVerbose | LiteTaskResponse:
        """Get details for a specific task."""
        task_id = task_id or self.trajectory_id
        url = f"/v0.1/trajectories/{task_id}"
        full_url = f"{self.base_url}{url}"

        with (
            external_trace(
                url=full_url,
                method="GET",
                library="httpx",
                custom_params={
                    "operation": "get_job",
                    "job_id": task_id,
                },
            ),
            self.client.stream(
                "GET", url, params={"history": history, "lite": lite}
            ) as response,
        ):
            if response.status_code in {401, 403}:
                raise PermissionError(
                    f"Error getting task: Permission denied for task {task_id}"
                )
            response.raise_for_status()
            json_data = "".join(response.iter_text(chunk_size=1024))
            data = json.loads(json_data)
            if "id" not in data:
                data["id"] = task_id

            if lite:
                return LiteTaskResponse(**data)

            verbose_response = TaskResponseVerbose(**data)

        if verbose:
            return verbose_response
        return JobNames.get_response_object_from_job(verbose_response.job_name)(**data)

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def aget_task(
        self,
        task_id: str | None = None,
        history: bool = False,
        verbose: bool = False,
        lite: bool = False,
    ) -> TaskResponse | TaskResponseVerbose | LiteTaskResponse:
        """Get details for a specific task asynchronously."""
        task_id = task_id or self.trajectory_id
        url = f"/v0.1/trajectories/{task_id}"
        full_url = f"{self.base_url}{url}"

        with external_trace(
            url=full_url,
            method="GET",
            library="httpx",
            custom_params={
                "operation": "get_job",
                "job_id": task_id,
            },
        ):
            async with self.async_client.stream(
                "GET", url, params={"history": history, "lite": lite}
            ) as response:
                if response.status_code in {401, 403}:
                    raise PermissionError(
                        f"Error getting task: Permission denied for task {task_id}."
                    )
                response.raise_for_status()
                json_data = "".join([chunk async for chunk in response.aiter_text()])
                data = json.loads(json_data)
                if "id" not in data:
                    data["id"] = task_id

                if lite:
                    return LiteTaskResponse(**data)

                verbose_response = TaskResponseVerbose(**data)

        if verbose:
            return verbose_response
        return JobNames.get_response_object_from_job(verbose_response.job_name)(**data)

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def cancel_task(self, task_id: str | None = None) -> bool:
        """Cancel a specific task/trajectory."""
        task_id = task_id or self.trajectory_id
        url = f"/v0.1/trajectories/{task_id}/cancel"
        full_url = f"{self.base_url}{url}"

        with external_trace(
            url=full_url,
            method="POST",
            library="httpx",
            custom_params={
                "operation": "cancel_job",
                "job_id": task_id,
            },
        ):
            get_task_response = self.get_task(task_id)
            # cancel if task is in progress
            if get_task_response.status == ExecutionStatus.IN_PROGRESS.value:
                response = self.client.post(url)
                try:
                    response.raise_for_status()

                except HTTPStatusError as e:
                    if e.response.status_code in {
                        HTTPStatus.UNAUTHORIZED,
                        HTTPStatus.FORBIDDEN,
                    }:
                        raise PermissionError(
                            f"Error canceling task: Permission denied for task {task_id}"
                        ) from e
                    if e.response.status_code == HTTPStatus.NOT_FOUND:
                        raise TaskFetchError(
                            f"Error canceling task: Trajectory not found for task {task_id}"
                        ) from e
                    raise

                get_task_response = self.get_task(task_id)
                return get_task_response.status == ExecutionStatus.CANCELLED.value
        return False

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def create_task(
        self,
        task_data: TaskRequest | dict[str, Any],
        files: list[str] | None = None,
    ):
        """Create a new futurehouse task.

        Args:
            task_data: The task request data
            files: Optional list of data_entry URIs to attach as files (e.g., ['data_entry:uuid'])
        """
        if isinstance(task_data, dict):
            task_data = TaskRequest.model_validate(task_data)

        self._validate_and_add_file_uris(files, task_data)

        if isinstance(task_data.name, JobNames):
            task_data.name = task_data.name.from_stage(
                task_data.name.name,
                self.stage,
            )

        response = self.client.post(
            "/v0.1/crows", json=task_data.model_dump(mode="json", by_alias=True)
        )
        if response.status_code in {401, 403}:
            raise PermissionError(
                f"Error creating task: Permission denied for task {task_data.name}."
            )
        response.raise_for_status()
        trajectory_id = response.json()["trajectory_id"]
        self.trajectory_id = trajectory_id  # pylint: disable=attribute-defined-outside-init
        return trajectory_id

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def acreate_task(
        self,
        task_data: TaskRequest | dict[str, Any],
        files: list[str] | None = None,
    ):
        """Create a new futurehouse task.

        Args:
            task_data: The task request data
            files: Optional list of data_entry URIs to attach as files (e.g., ['data_entry:uuid'])
        """
        if isinstance(task_data, dict):
            task_data = TaskRequest.model_validate(task_data)

        self._validate_and_add_file_uris(files, task_data)

        if isinstance(task_data.name, JobNames):
            task_data.name = task_data.name.from_stage(
                task_data.name.name,
                self.stage,
            )

        response = await self.async_client.post(
            "/v0.1/crows", json=task_data.model_dump(mode="json", by_alias=True)
        )
        if response.status_code in {401, 403}:
            raise PermissionError(
                f"Error creating task: Permission denied for task {task_data.name}."
            )
        response.raise_for_status()
        trajectory_id = response.json()["trajectory_id"]
        self.trajectory_id = trajectory_id  # pylint: disable=attribute-defined-outside-init
        return trajectory_id

    @staticmethod
    def _validate_and_add_file_uris(files, task_data):
        if files:
            # Add files into environment_config if provided
            if task_data.runtime_config is None:
                task_data.runtime_config = RuntimeConfig()
            if task_data.runtime_config.environment_config is None:
                task_data.runtime_config.environment_config = {}

            if task_data.runtime_config.environment_config.get(
                "data_storage_uris", None
            ):
                raise ValueError(
                    "Please provide file uris either in the files parameter or within the environment configuration, not both."
                )

            task_data.runtime_config.environment_config["data_storage_uris"] = files

    async def arun_tasks_until_done(
        self,
        task_data: (
            TaskRequest
            | dict[str, Any]
            | Collection[TaskRequest]
            | Collection[dict[str, Any]]
        ),
        *,
        verbose: bool = False,
        progress_bar: bool = False,
        concurrency: int = 10,
        timeout: float | None = DEFAULT_AGENT_TIMEOUT,
        files: list[str] | None = None,
    ) -> list[LiteTaskResponse | TaskResponse | TaskResponseVerbose]:
        # Convert single task to collection
        is_single_task = isinstance(task_data, dict) or not isinstance(
            task_data, Collection
        )
        all_tasks: Collection[TaskRequest | dict[str, Any]] = (
            cast(Collection[TaskRequest | dict[str, Any]], [task_data])
            if is_single_task
            else cast(Collection[TaskRequest | dict[str, Any]], task_data)
        )

        trajectory_ids = await gather_with_concurrency(
            concurrency,
            [self.acreate_task(task, files=files) for task in all_tasks],
            progress=progress_bar,
        )

        start_time = time.monotonic()
        completed_tasks: dict[str, LiteTaskResponse | TaskResponse] = {}

        if progress_bar:
            progress = tqdm(
                total=len(trajectory_ids), desc="Waiting for tasks to finish", ncols=0
            )

        while timeout is None or (time.monotonic() - start_time) < timeout:
            task_results = await gather_with_concurrency(
                concurrency,
                [
                    self.aget_task(task_id, verbose=verbose, lite=True)
                    for task_id in trajectory_ids
                    if task_id not in completed_tasks
                ],
            )

            for task in task_results:
                task_id = str(task.task_id)
                if (
                    task_id not in completed_tasks
                    and ExecutionStatus(task.status).is_terminal_state()
                ):
                    # on completion fetches the full state and messages of the task
                    completed_tasks[task_id] = await self.aget_task(
                        task_id=task_id,
                        lite=False,
                        verbose=verbose,
                    )
                    if progress_bar:
                        progress.update(1)

            all_done = len(completed_tasks) == len(trajectory_ids)

            if all_done:
                break
            await asyncio.sleep(self.DEFAULT_POLLING_TIME)

        else:
            logger.warning(
                f"Timed out waiting for tasks to finish after {timeout} seconds. Returning with {len(completed_tasks)} completed tasks and {len(trajectory_ids)} total tasks."
            )

        if progress_bar:
            progress.close()

        return [
            completed_tasks.get(task_id)
            or (await self.aget_task(task_id, verbose=verbose))
            for task_id in trajectory_ids
        ]

    def run_tasks_until_done(
        self,
        task_data: (
            TaskRequest
            | dict[str, Any]
            | Collection[TaskRequest]
            | Collection[dict[str, Any]]
        ),
        verbose: bool = False,
        progress_bar: bool = False,
        timeout: float | None = DEFAULT_AGENT_TIMEOUT,
        files: list[str] | None = None,
    ) -> list[LiteTaskResponse | TaskResponse | TaskResponseVerbose]:
        """Run multiple tasks and wait for them to complete.

        Args:
            task_data: A single task or collection of tasks to run
            verbose: Whether to return verbose task responses
            progress_bar: Whether to display a progress bar
            timeout: Maximum time to wait for task completion in seconds,
                or wait indefinitely if None.
            files: Optional list of data_entry URIs to attach as files (only for single task)

        Returns:
            A list of completed task responses
        """
        # Convert single task to collection
        is_single_task = isinstance(task_data, dict) or not isinstance(
            task_data, Collection
        )
        all_tasks: Collection[TaskRequest | dict[str, Any]] = (
            cast(Collection[TaskRequest | dict[str, Any]], [task_data])
            if is_single_task
            else cast(Collection[TaskRequest | dict[str, Any]], task_data)
        )

        # If files are provided and it's a single task, pass files to create_task
        trajectory_ids = [self.create_task(task, files=files) for task in all_tasks]

        start_time = time.monotonic()
        completed_tasks: dict[str, LiteTaskResponse | TaskResponse] = {}

        if progress_bar:
            progress = sync_tqdm(
                total=len(trajectory_ids), desc="Waiting for tasks to finish", ncols=0
            )

        while timeout is None or (time.monotonic() - start_time) < timeout:
            all_done = True

            for task_id in trajectory_ids:
                if task_id in completed_tasks:
                    continue

                task = self.get_task(task_id, verbose=verbose, lite=True)

                if not ExecutionStatus(task.status).is_terminal_state():
                    all_done = False
                elif task_id not in completed_tasks:
                    completed_tasks[task_id] = self.get_task(
                        task_id=task_id,
                        lite=False,
                        verbose=verbose,
                    )
                    if progress_bar:
                        progress.update(1)

            if all_done:
                break
            time.sleep(self.DEFAULT_POLLING_TIME)

        else:
            logger.warning(
                f"Timed out waiting for tasks to finish after {timeout} seconds. Returning with {len(completed_tasks)} completed tasks and {len(trajectory_ids)} total tasks."
            )

        if progress_bar:
            progress.close()

        return [
            completed_tasks.get(task_id) or self.get_task(task_id, verbose=verbose)
            for task_id in trajectory_ids
        ]

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_build_status(self, build_id: UUID | None = None) -> dict[str, Any]:
        """Get the status of a build."""
        build_id = build_id or self.build_id
        response = self.client.get(f"/v0.1/builds/{build_id}")
        response.raise_for_status()
        return response.json()

    # TODO: Refactor later so we don't have to ignore PLR0915
    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def create_job(self, config: JobDeploymentConfig) -> dict[str, Any]:  # noqa: PLR0914
        """Creates a futurehouse job deployment from the environment and environment files.

        Args:
            config: Configuration object containing all necessary parameters for job deployment.

        Returns:
            A response object containing metadata of the build.

        """
        task_description: str = config.task_description or str(
            fetch_environment_function_docstring(
                config.environment,
                config.path,  # type: ignore[arg-type]
                "from_task",
            )
            if config.functional_environment is None
            else config.functional_environment.start_fn.__doc__
        )
        if not task_description or not task_description.strip():
            raise InvalidTaskDescriptionError(
                "Task description cannot be None or empty. Ensure your from_task environment function has a valid docstring."
                " If you are deploying with your Environment as a dependency, "
                "you must add a `task_description` to your `JobDeploymentConfig`.",
            )
        selected_org = OrganizationSelector.select_organization(self.organizations)
        if selected_org is None:
            return {
                "status": "cancelled",
                "message": "Organization selection cancelled",
            }
        try:
            try:
                job_status = self._check_job(config.job_name, selected_org)
                if job_status["exists"]:
                    if config.force:
                        logger.warning(
                            f"Overwriting existing deployment '{job_status['name']}'"
                        )
                    else:
                        user_response = input(
                            f"A deployment named '{config.job_name}' already exists. Do you want to proceed? [y/N]: "
                        )
                        if user_response.lower() != "y":
                            logger.info("Deployment cancelled.")
                            return {
                                "status": "cancelled",
                                "message": "User cancelled deployment",
                            }
            except Exception:
                logger.warning("Unable to check for existing deployment, proceeding.")
            encoded_pickle = None
            if config.functional_environment is not None:
                # TODO(remo): change aviary fenv code to have this happen automatically.
                for t in config.functional_environment.tools:
                    t._force_pickle_fn = True
                pickled_env = cloudpickle.dumps(config.functional_environment)
                encoded_pickle = base64.b64encode(pickled_env).decode("utf-8")
            files = []
            ignore_parts = set(FILE_UPLOAD_IGNORE_PARTS) | set(config.ignore_dirs or [])
            for file_path in Path(config.path).rglob("*") if config.path else []:
                if any(ignore in file_path.parts for ignore in ignore_parts):
                    continue

                if file_path.is_file():
                    relative_path = (
                        f"{config.module_name}/{file_path.relative_to(config.path)}"  # type: ignore[arg-type]
                    )
                    files.append(
                        (
                            "files",
                            (
                                relative_path,
                                file_path.read_bytes(),
                                "application/octet-stream",
                            ),
                        ),
                    )
            if (
                config.functional_environment is not None
                and config.requirements is not None
            ):
                requirements_content = "\n".join(config.requirements)
                files.append(
                    (
                        "files",
                        (
                            f"{config.environment}/requirements.txt",
                            requirements_content.encode(),
                            "text/plain",
                        ),
                    ),
                )
            if config.requirements_path:
                requirements_path = Path(config.requirements_path)
                files.append(
                    (
                        "files",
                        (
                            f"{config.module_name}/{requirements_path.name}",
                            requirements_path.read_bytes(),
                            "application/octet-stream",
                        ),
                    ),
                )
            if config.path:
                self._validate_files(files, config.path)
            markdown_template_file = None
            if config.markdown_template_path:
                self._validate_template_path(config.markdown_template_path)
                template_path = Path(config.markdown_template_path)
                markdown_template_file = (
                    "files",
                    (
                        "markdown_template",
                        template_path.read_bytes(),
                        "application/octet-stream",
                    ),
                )
            logger.debug(f"Sending files: {[f[1][0] for f in files]}")
            data = {
                "agent": (
                    config.agent.model_dump_json()
                    if isinstance(config.agent, AgentConfig)
                    else config.agent
                ),
                "job_name": config.job_name,
                "organization": selected_org,
                "environment": config.environment,
                "functional_environment_pickle": encoded_pickle,
                "python_version": config.python_version,
                "task_description": task_description,
                "environment_variables": (
                    json.dumps(config.environment_variables)
                    if config.environment_variables
                    else None
                ),
                "container_config": (
                    config.container_config.model_dump_json()
                    if config.container_config
                    else None
                ),
                "timeout": config.timeout,
                "frame_paths": (
                    json.dumps(
                        [fp.model_dump() for fp in config.frame_paths],
                    )
                    if config.frame_paths
                    else None
                ),
                "task_queues_config": (
                    config.task_queues_config.model_dump_json()
                    if config.task_queues_config
                    else None
                ),
                "user_input_config": (
                    json.dumps([
                        entity.model_dump() for entity in config.user_input_config
                    ])
                    if config.user_input_config
                    else None
                ),
                "cache_strategy": config.cache_strategy,
            }
            # Only include max_steps if it's not None to prevent empty string in multipart encoding
            if config.max_steps is not None:
                data["max_steps"] = config.max_steps
            response = self.multipart_client.post(
                "/v0.1/builds",
                data=data,
                files=(
                    [*files, markdown_template_file]
                    if markdown_template_file
                    else files
                ),
                headers={"Accept": "application/json"},
                params={"internal-deps": config.requires_aviary_internal},
            )
            try:
                response.raise_for_status()
                build_context = response.json()
                self.build_id = build_context["build_id"]  # pylint: disable=attribute-defined-outside-init
            except HTTPStatusError as e:
                error_detail = response.json()
                error_message = error_detail.get("detail", str(e))
                raise JobCreationError(
                    f"Server validation error: {error_message}."
                ) from e
        except Exception as e:
            raise JobCreationError(f"Error generating docker image: {e!r}.") from e
        return build_context

    # TODO: we should have have an async upload_file, check_assembly_status,
    # wait_for_assembly_completion, upload_directory, upload_single_file
    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def upload_file(  # noqa: PLR0917
        self,
        file_path: str | os.PathLike,
        name: str | None = None,
        description: str | None = None,
        project_id: UUID | None = None,
        dataset_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Upload a file or directory using the data storage service.

        Args:
            file_path: The local path to the file or directory to upload.
            name: Name for the data storage entry (defaults to filename).
            description: Optional description of the file.
            project_id: ID of the project this file belongs to.
            dataset_id: ID of the dataset this file belongs to.
            metadata: Optional metadata for the file.
            tags: Optional tags for the file.

        Returns:
            Data entry URI in format "data_entry:{uuid}" for use in
            runtime_config.data_storage_uris when submitting tasks.

        Raises:
            FileNotFoundError: If the file or directory does not exist.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File or directory not found: {file_path}")

        if name is None:
            name = file_path.name

        # Use the data storage methods from the mixin
        response = self.store_file_content(
            name=name,
            file_path=file_path,
            description=description,
            project_id=project_id,
            dataset_id=dataset_id,
            metadata=metadata,
            tags=tags,
        )

        logger.info(
            f"Successfully uploaded {file_path} as data_entry:{response.data_storage.id}"
        )
        return f"data_entry:{response.data_storage.id}"

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def list_files(
        self,
        trajectory_id: str,
    ) -> list[dict[str, Any]]:
        """List files associated with a trajectory using the provenance API.

        Args:
            trajectory_id: The specific trajectory id to list files from.

        Returns:
            List of data storage provenance entries with full entry details.
            Each entry contains provenance info and the associated data_storage object.

        Raises:
            RestClientError: If there is an error listing the files.
        """
        try:
            url = "/v0.1/data-storage/provenance/data-entries"
            # Note: Backend uses aliases - actor_ids -> actor_id, operations -> operation
            params: dict[str, list[str] | bool] = {
                "actor_id": [trajectory_id],  # List format for Query alias
                "operation": [
                    "create"
                ],  # Lowercase: create, update, delete, read, download
                "include_entry_data": True,
            }

            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            logger.exception(
                f"Error listing files for trajectory {trajectory_id}: {e.response.text}"
            )
            raise RestClientError(
                f"Error listing files: {e.response.status_code} - {e.response.text}."
            ) from e
        except Exception as e:
            logger.exception(f"Error listing files for trajectory {trajectory_id}")
            raise RestClientError(f"Error listing files: {e!r}.") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_world_model(
        self, world_model_id: UUID | None = None, name: str | None = None
    ) -> WorldModelResponse:
        """Get a world model snapshot by its ID or name.

        Args:
            world_model_id: The unique ID of the world model snapshot.
            name: The name of the world model to get the latest version of.

        Returns:
            The requested world model snapshot.

        Raises:
            ValueError: If neither or both `world_model_id` and `name` are provided.
            WorldModelFetchError: If the API call fails or the model is not found.
        """
        if not (world_model_id or name) or (world_model_id and name):
            raise ValueError("Provide either 'world_model_id' or 'name', but not both.")

        try:
            identifier = str(world_model_id) if world_model_id else name
            response = self.client.get(f"/v0.1/world-models/{identifier}")
            response.raise_for_status()
            return WorldModelResponse.model_validate(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise WorldModelFetchError(
                    "World model not found with the specified identifier."
                ) from e
            raise WorldModelFetchError(
                f"Error fetching world model: {e.response.status_code} - {e.response.text}."
            ) from e
        except Exception as e:
            raise WorldModelFetchError(f"An unexpected error occurred: {e!r}.") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def aget_world_model(
        self, world_model_id: UUID | None = None, name: str | None = None
    ) -> WorldModelResponse:
        """Asynchronously get a world model snapshot by its ID or name.

        Args:
            world_model_id: The unique ID of the world model snapshot.
            name: The name of the world model to get the latest version of.

        Returns:
            The requested world model snapshot.

        Raises:
            ValueError: If neither or both `world_model_id` and `name` are provided.
            WorldModelFetchError: If the API call fails or the model is not found.
        """
        if not (world_model_id or name) or (world_model_id and name):
            raise ValueError("Provide either 'world_model_id' or 'name', but not both.")

        try:
            identifier = str(world_model_id) if world_model_id else name
            response = await self.async_client.get(f"/v0.1/world-models/{identifier}")
            response.raise_for_status()
            return WorldModelResponse.model_validate(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise WorldModelFetchError(
                    "World model not found with the specified identifier."
                ) from e
            raise WorldModelFetchError(
                f"Error fetching world model: {e.response.status_code} - {e.response.text}."
            ) from e
        except Exception as e:
            raise WorldModelFetchError(f"An unexpected error occurred: {e!r}.") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
    )
    def list_world_models(
        self,
        name: str | None = None,
        project_id: UUID | str | None = None,
        limit: int = 150,
        offset: int = 0,
        sort_order: str = "asc",
    ) -> list[WorldModelResponse]:
        """List world models with different behavior based on filters.

        When filtering by name: returns only the latest version for that name.
        When filtering by project_id (without name): returns all versions for that project.
        When no filters: returns latest version of each world model.

        Args:
            name: Filter by world model name.
            project_id: Filter by project ID.
            limit: The maximum number of models to return.
            offset: Number of results to skip for pagination.
            sort_order: Sort order 'asc' or 'desc'.

        Returns:
            A list of world model dictionaries.
        """
        try:
            params: dict[str, str | int] = {
                "limit": limit,
                "offset": offset,
                "sort_order": sort_order,
            }
            if name:
                params["name"] = name
            if project_id:
                params["project_id"] = str(project_id)

            response = self.client.get("/v0.1/world-models", params=params)
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            raise WorldModelFetchError(
                f"Error listing world models: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise WorldModelFetchError(f"An unexpected error occurred: {e!r}.") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
    )
    def search_world_models(
        self,
        criteria: list[SearchCriterion] | None = None,
        size: int = 10,
        project_id: UUID | str | None = None,
        search_all_versions: bool = False,
    ) -> list[WorldModelResponse]:
        """Search world models using structured criteria.

        Args:
            criteria: List of SearchCriterion objects with field, operator, and value.
            size: The number of results to return.
            project_id: Optional filter by project ID.
            search_all_versions: Whether to search all versions or just latest.

        Returns:
            A list of world model responses.

        Example:
            from edison_client.models.rest import SearchCriterion, SearchOperator
            criteria = [
                SearchCriterion(field="name", operator=SearchOperator.CONTAINS, value="chemistry"),
                SearchCriterion(field="email", operator=SearchOperator.CONTAINS, value="tyler"),
            ]
            results = client.search_world_models(criteria=criteria, size=20)
        """
        try:
            payload = WorldModelSearchPayload(
                criteria=criteria or [],
                size=size,
                project_id=project_id,
                search_all_versions=search_all_versions,
            )

            response = self.client.post(
                "/v0.1/world-models/search",
                json=payload.model_dump(mode="json"),
            )
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            raise WorldModelFetchError(
                f"Error searching world models: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise WorldModelFetchError(f"An unexpected error occurred: {e!r}.") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def create_world_model(self, payload: WorldModel) -> UUID:
        """Create a new, immutable world model snapshot.

        Args:
            payload: An instance of WorldModel with the snapshot's data.

        Returns:
            The UUID of the newly created world model.

        Raises:
            WorldModelCreationError: If the API call fails.
        """
        try:
            response = self.client.post(
                "/v0.1/world-models", json=payload.model_dump(mode="json")
            )
            response.raise_for_status()
            # The server returns a raw UUID string in the body
            return UUID(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.BAD_REQUEST:
                raise WorldModelCreationError(
                    f"Invalid payload for world model creation: {e.response.text}."
                ) from e
            raise WorldModelCreationError(
                f"Error creating world model: {e.response.status_code} - {e.response.text}."
            ) from e
        except Exception as e:
            raise WorldModelCreationError(
                f"An unexpected error occurred during world model creation: {e!r}."
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def acreate_world_model(self, payload: WorldModel) -> UUID:
        """Asynchronously create a new, immutable world model snapshot.

        Args:
            payload: An instance of WorldModel with the snapshot's data.

        Returns:
            The UUID of the newly created world model.

        Raises:
            WorldModelCreationError: If the API call fails.
        """
        try:
            response = await self.async_client.post(
                "/v0.1/world-models", json=payload.model_dump(mode="json")
            )
            response.raise_for_status()
            return UUID(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.BAD_REQUEST:
                raise WorldModelCreationError(
                    f"Invalid payload for world model creation: {e.response.text}."
                ) from e
            raise WorldModelCreationError(
                f"Error creating world model: {e.response.status_code} - {e.response.text}."
            ) from e
        except Exception as e:
            raise WorldModelCreationError(
                f"An unexpected error occurred during world model creation: {e!r}."
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
    )
    async def delete_world_model(self, world_model_id: UUID) -> None:
        """Delete a world model snapshot by its ID.

        Args:
            world_model_id: The unique ID of the world model snapshot to delete.

        Raises:
            WorldModelDeletionError: If the API call fails.
        """
        try:
            response = await self.async_client.delete(
                f"/v0.1/world-models/{world_model_id}"
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            raise WorldModelDeletionError(
                f"Error deleting world model: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise WorldModelDeletionError(f"An unexpected error occurred: {e}") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
    )
    def get_project_by_name(self, name: str, limit: int = 2) -> UUID | list[UUID]:
        """Get a project UUID by name.

        Args:
            name: The name of the project to find
            limit: Maximum number of projects to return

        Returns:
            UUID of the project as a string or a list of UUIDs if multiple projects are found
        """
        try:
            response = self.client.get(
                "/v0.1/projects", params={"limit": limit, "name": name}
            )
            response.raise_for_status()
            projects = response.json()
        except HTTPStatusError as e:
            raise ProjectError(
                f"Error getting project by name: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise ProjectError(f"Error getting project by name: {e}") from e
        if len(projects) == 0:
            raise ProjectError(f"No project found with name '{name}'")
        if len(projects) > 1:
            logger.warning(
                f"Multiple projects found with name '{name}'. Found {len(projects)} projects."
            )

        ids = [UUID(project["id"]) for project in projects]
        return ids[0] if len(ids) == 1 else ids

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
    )
    async def aget_project_by_name(
        self, name: str, limit: int = 2
    ) -> UUID | list[UUID]:
        """Asynchronously get a project UUID by name.

        Args:
            name: The name of the project to find
            limit: Maximum number of projects to return

        Returns:
            UUID of the project as a string or a list of UUIDs if multiple projects are found
        """
        try:
            response = await self.async_client.get(
                "/v0.1/projects", params={"limit": limit, "name": name}
            )
            response.raise_for_status()
            projects = response.json()
        except Exception as e:
            raise ProjectError(f"Error getting project by name: {e}") from e
        if len(projects) == 0:
            raise ProjectError(f"No project found with name '{name}'")
        if len(projects) > 1:
            logger.warning(
                f"Multiple projects found with name '{name}'. Found {len(projects)} projects."
            )

        ids = [UUID(project["id"]) for project in projects]
        return ids[0] if len(ids) == 1 else ids

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
    )
    def create_project(
        self,
        name: str,
        share_status: ShareStatus = ShareStatus.PRIVATE,
        permitted_accessors: PermittedAccessors | None = None,
        metadata: dict | None = None,
    ) -> UUID:
        """Create a new project.

        Args:
            name: The name for the project
            share_status: Share status for the project (private, shared, or public)
            permitted_accessors: Permitted accessors for the project (only valid when share_status is SHARED)
            metadata: Metadata for the project

        Returns:
            UUID of the created project.

        Raises:
            ProjectError: If there's an error creating the project
        """
        try:
            data: dict[str, Any] = {
                "name": name,
                "share_status": share_status,
                "metadata": metadata,
            }
            if permitted_accessors is not None:
                data["permitted_accessors"] = permitted_accessors.model_dump()
            response = self.client.post("/v0.1/projects", json=data)
            response.raise_for_status()
            return UUID(response.json())
        except HTTPStatusError as e:
            raise ProjectError(
                f"Error creating project: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise ProjectError(f"Error creating project: {e}") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
    )
    def add_task_to_project(self, project_id: UUID, trajectory_id: str) -> None:
        """Add a trajectory to a project.

        Args:
            project_id: The UUID of the project
            trajectory_id: The UUID of the trajectory to add

        Raises:
            ProjectError: If there's an error adding the trajectory to the project
        """
        try:
            data = {"trajectory_id": trajectory_id}
            response = self.client.post(
                f"/v0.1/projects/{project_id}/trajectories", json=data
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise ProjectError(
                    f"Project {project_id} or trajectory {trajectory_id} not found"
                ) from e
            if e.response.status_code == codes.FORBIDDEN:
                raise ProjectError(
                    f"Permission denied to add trajectory to project {project_id}"
                ) from e
            raise ProjectError(
                f"Error adding trajectory to project: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise ProjectError(f"Error adding trajectory to project: {e}") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
    )
    async def acreate_project(
        self,
        name: str,
        share_status: ShareStatus = ShareStatus.PRIVATE,
        permitted_accessors: PermittedAccessors | None = None,
        metadata: dict | None = None,
    ) -> UUID:
        """Asynchronously create a new project.

        Args:
            name: The name for the project
            share_status: Share status for the project (private, shared, or public)
            permitted_accessors: Permitted accessors for the project (only valid when share_status is SHARED)
            metadata: Metadata for the project

        Returns:
            UUID of the created project.

        Raises:
            ProjectError: If there's an error creating the project
        """
        try:
            data: dict[str, Any] = {
                "name": name,
                "share_status": share_status,
                "metadata": metadata,
            }
            if permitted_accessors is not None:
                data["permitted_accessors"] = permitted_accessors.model_dump()
            response = await self.async_client.post("/v0.1/projects", json=data)
            response.raise_for_status()
            return UUID(response.json())
        except HTTPStatusError as e:
            raise ProjectError(
                f"Error creating project: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise ProjectError(f"Error creating project: {e}") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
    )
    async def aadd_task_to_project(self, project_id: UUID, trajectory_id: str) -> None:
        """Asynchronously add a trajectory to a project.

        Args:
            project_id: The UUID of the project
            trajectory_id: The UUID of the trajectory to add

        Raises:
            ProjectError: If there's an error adding the trajectory to the project
        """
        try:
            data = {"trajectory_id": trajectory_id}
            response = await self.async_client.post(
                f"/v0.1/projects/{project_id}/trajectories", json=data
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise ProjectError(
                    f"Project {project_id} or trajectory {trajectory_id} not found"
                ) from e
            if e.response.status_code == codes.FORBIDDEN:
                raise ProjectError(
                    f"Permission denied to add trajectory to project {project_id}"
                ) from e
            raise ProjectError(
                f"Error adding trajectory to project: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise ProjectError(f"Error adding trajectory to project: {e}") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_tasks(
        self,
        query_params: TrajectoryQueryParams | None = None,
        *,
        project_id: UUID | None = None,
        name: str | None = None,
        user: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        """Fetches trajectories with applied filtering.

        Args:
            query_params: Optional TrajectoryQueryParams model with all parameters
            project_id: Optional project ID to filter trajectories by
            name: Optional name filter for trajectories
            user: Optional user email filter for trajectories
            limit: Maximum number of trajectories to return (default: 50, max: 200)
            offset: Number of trajectories to skip for pagination (default: 0)
            sort_by: Field to sort by, either "created_at" or "name" (default: "created_at")
            sort_order: Sort order, either "asc" or "desc" (default: "desc")

        Returns:
            List of trajectory dictionaries

        Raises:
            TaskFetchError: If there's an error fetching trajectories
        """
        try:
            if query_params is not None:
                params = query_params.to_query_params()
            else:
                params_model = TrajectoryQueryParams(
                    project_id=project_id,
                    name=name,
                    user=user,
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_order=sort_order,
                )
                params = params_model.to_query_params()

            response = self.client.get("/v0.1/trajectories", params=params)
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            if e.response.status_code in {401, 403}:
                raise PermissionError(
                    "Error getting trajectories: Permission denied"
                ) from e
            raise TaskFetchError(
                f"Error getting trajectories: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise TaskFetchError(f"Error getting trajectories: {e!r}") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def aget_tasks(
        self,
        query_params: TrajectoryQueryParams | None = None,
        *,
        project_id: UUID | None = None,
        name: str | None = None,
        user: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        """Asynchronously fetch trajectories with applied filtering.

        Args:
            query_params: Optional TrajectoryQueryParams model with all parameters
            project_id: Optional project ID to filter trajectories by
            name: Optional name filter for trajectories
            user: Optional user email filter for trajectories
            limit: Maximum number of trajectories to return (default: 50, max: 200)
            offset: Number of trajectories to skip for pagination (default: 0)
            sort_by: Field to sort by, either "created_at" or "name" (default: "created_at")
            sort_order: Sort order, either "asc" or "desc" (default: "desc")

        Returns:
            List of trajectory dictionaries

        Raises:
            TaskFetchError: If there's an error fetching trajectories
        """
        try:
            if query_params is not None:
                params = query_params.to_query_params()
            else:
                params_model = TrajectoryQueryParams(
                    project_id=project_id,
                    name=name,
                    user=user,
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_order=sort_order,
                )
                params = params_model.to_query_params()

            response = await self.async_client.get("/v0.1/trajectories", params=params)
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            if e.response.status_code in {401, 403}:
                raise PermissionError(
                    "Error getting trajectories: Permission denied"
                ) from e
            raise TaskFetchError(
                f"Error getting trajectories: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise TaskFetchError(f"Error getting trajectories: {e!r}") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def list_user_agent_requests(
        self,
        user_id: str | None = None,
        trajectory_id: UUID | None = None,
        request_status: UserAgentRequestStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UserAgentRequest]:
        """List user agent requests with optional filters.

        Args:
            user_id: Filter requests by user ID. Defaults to the authenticated user's ID if not provided.
            trajectory_id: Filter requests by trajectory ID.
            request_status: Filter requests by status (e.g., PENDING).
            limit: Maximum number of requests to return.
            offset: Offset for pagination.

        Returns:
            A list of user agent requests.

        Raises:
            UserAgentRequestFetchError: If the API call fails.
        """
        params = {
            "user_id": user_id,
            "trajectory_id": str(trajectory_id) if trajectory_id else None,
            "request_status": request_status.value if request_status else None,
            "limit": limit,
            "offset": offset,
        }
        # Filter out None values
        params = {k: v for k, v in params.items() if v is not None}
        try:
            response = self.client.get("/v0.1/user-agent-requests", params=params)
            response.raise_for_status()
            return [UserAgentRequest.model_validate(item) for item in response.json()]
        except HTTPStatusError as e:
            raise UserAgentRequestFetchError(
                f"Error listing user agent requests: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise UserAgentRequestFetchError(
                f"An unexpected error occurred: {e!r}"
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def alist_user_agent_requests(
        self,
        user_id: str | None = None,
        trajectory_id: UUID | None = None,
        request_status: UserAgentRequestStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UserAgentRequest]:
        """Asynchronously list user agent requests with optional filters.

        Args:
            user_id: Filter requests by user ID. Defaults to the authenticated user's ID if not provided.
            trajectory_id: Filter requests by trajectory ID.
            request_status: Filter requests by status (e.g., PENDING).
            limit: Maximum number of requests to return.
            offset: Offset for pagination.

        Returns:
            A list of user agent requests.

        Raises:
            UserAgentRequestFetchError: If the API call fails.
        """
        params = {
            "user_id": user_id,
            "trajectory_id": str(trajectory_id) if trajectory_id else None,
            "request_status": request_status.value if request_status else None,
            "limit": limit,
            "offset": offset,
        }
        # Filter out None values
        params = {k: v for k, v in params.items() if v is not None}
        try:
            response = await self.async_client.get(
                "/v0.1/user-agent-requests", params=params
            )
            response.raise_for_status()
            return [UserAgentRequest.model_validate(item) for item in response.json()]
        except HTTPStatusError as e:
            raise UserAgentRequestFetchError(
                f"Error listing user agent requests: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise UserAgentRequestFetchError(
                f"An unexpected error occurred: {e!r}"
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_user_agent_request(self, request_id: UUID) -> UserAgentRequest:
        """Retrieve a single user agent request by its unique ID.

        Args:
            request_id: The unique ID of the request.

        Returns:
            The user agent request.

        Raises:
            UserAgentRequestFetchError: If the API call fails or the request is not found.
        """
        try:
            response = self.client.get(f"/v0.1/user-agent-requests/{request_id}")
            response.raise_for_status()
            return UserAgentRequest.model_validate(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise UserAgentRequestFetchError(
                    f"User agent request with ID {request_id} not found."
                ) from e
            raise UserAgentRequestFetchError(
                f"Error fetching user agent request: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise UserAgentRequestFetchError(
                f"An unexpected error occurred: {e!r}"
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def aget_user_agent_request(self, request_id: UUID) -> UserAgentRequest:
        """Asynchronously retrieve a single user agent request by its unique ID.

        Args:
            request_id: The unique ID of the request.

        Returns:
            The user agent request.

        Raises:
            UserAgentRequestFetchError: If the API call fails or the request is not found.
        """
        try:
            response = await self.async_client.get(
                f"/v0.1/user-agent-requests/{request_id}"
            )
            response.raise_for_status()
            return UserAgentRequest.model_validate(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise UserAgentRequestFetchError(
                    f"User agent request with ID {request_id} not found."
                ) from e
            raise UserAgentRequestFetchError(
                f"Error fetching user agent request: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise UserAgentRequestFetchError(
                f"An unexpected error occurred: {e!r}"
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def create_user_agent_request(self, payload: UserAgentRequestPostPayload) -> UUID:
        """Creates a new request from an agent to a user.

        Args:
            payload: An instance of UserAgentRequestPostPayload with the request data.

        Returns:
            The UUID of the newly created user agent request.

        Raises:
            UserAgentRequestCreationError: If the API call fails.
        """
        try:
            response = self.client.post(
                "/v0.1/user-agent-requests", json=payload.model_dump(mode="json")
            )
            response.raise_for_status()
            return UUID(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.UNPROCESSABLE_ENTITY:
                raise UserAgentRequestCreationError(
                    f"Invalid payload for user agent request creation: {e.response.text}."
                ) from e
            raise UserAgentRequestCreationError(
                f"Error creating user agent request: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise UserAgentRequestCreationError(
                f"An unexpected error occurred during user agent request creation: {e!r}."
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def acreate_user_agent_request(
        self, payload: UserAgentRequestPostPayload
    ) -> UUID:
        """Asynchronously creates a new request from an agent to a user.

        Args:
            payload: An instance of UserAgentRequestPostPayload with the request data.

        Returns:
            The UUID of the newly created user agent request.

        Raises:
            UserAgentRequestCreationError: If the API call fails.
        """
        try:
            response = await self.async_client.post(
                "/v0.1/user-agent-requests", json=payload.model_dump(mode="json")
            )
            response.raise_for_status()
            return UUID(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.UNPROCESSABLE_ENTITY:
                raise UserAgentRequestCreationError(
                    f"Invalid payload for user agent request creation: {e.response.text}."
                ) from e
            raise UserAgentRequestCreationError(
                f"Error creating user agent request: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise UserAgentRequestCreationError(
                f"An unexpected error occurred during user agent request creation: {e!r}."
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def respond_to_user_agent_request(
        self, request_id: UUID, payload: UserAgentResponsePayload
    ) -> None:
        """Submit a user's response to a pending agent request.

        Args:
            request_id: The unique ID of the request to respond to.
            payload: An instance of UserAgentResponsePayload with the response data.

        Raises:
            UserAgentRequestResponseError: If the API call fails.
        """
        try:
            response = self.client.post(
                f"/v0.1/user-agent-requests/{request_id}/response",
                json=payload.model_dump(mode="json"),
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise UserAgentRequestResponseError(
                    f"User agent request with ID {request_id} not found."
                ) from e
            if e.response.status_code == codes.UNPROCESSABLE_ENTITY:
                raise UserAgentRequestResponseError(
                    f"Invalid response payload: {e.response.text}."
                ) from e
            raise UserAgentRequestResponseError(
                f"Error responding to user agent request: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise UserAgentRequestResponseError(
                f"An unexpected error occurred while responding to the request: {e!r}."
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def arespond_to_user_agent_request(
        self, request_id: UUID, payload: UserAgentResponsePayload
    ) -> None:
        """Asynchronously submit a user's response to a pending agent request.

        Args:
            request_id: The unique ID of the request to respond to.
            payload: An instance of UserAgentResponsePayload with the response data.

        Raises:
            UserAgentRequestResponseError: If the API call fails.
        """
        try:
            response = await self.async_client.post(
                f"/v0.1/user-agent-requests/{request_id}/response",
                json=payload.model_dump(mode="json"),
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise UserAgentRequestResponseError(
                    f"User agent request with ID {request_id} not found."
                ) from e
            if e.response.status_code == codes.UNPROCESSABLE_ENTITY:
                raise UserAgentRequestResponseError(
                    f"Invalid response payload: {e.response.text}."
                ) from e
            raise UserAgentRequestResponseError(
                f"Error responding to user agent request: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise UserAgentRequestResponseError(
                f"An unexpected error occurred while responding to the request: {e!r}."
            ) from e

    def create_discovery(  # noqa: PLR0917
        self,
        project_id: UUID,
        world_model_id: UUID,
        dataset_id: UUID,
        description: str,
        associated_trajectories: list[UUID],
        validation_level: int,
    ) -> UUID:
        """Create a new discovery.

        Args:
            project_id: The ID of the project the discovery is associated with.
            world_model_id: The ID of the world model the discovery is associated with.
            dataset_id: The ID of the dataset the discovery is associated with.
            description: The description of the discovery.
            associated_trajectories: The IDs of the trajectories to associate with the discovery.
            validation_level: The validation level of the discovery.

        Returns:
            The ID of the created discovery.

        Raises:
            DiscoveryCreationError: If there's an error creating the discovery.
        """
        try:
            data = {
                "project_id": str(project_id),
                "world_model_id": str(world_model_id),
                "dataset_id": str(dataset_id),
                "description": description,
                "associated_trajectories": [
                    str(trajectory) for trajectory in associated_trajectories
                ],
                "validation_level": validation_level,
            }
            response = self.client.post("/v0.1/discoveries", json=data)
            response.raise_for_status()
            return UUID(response.json())
        except HTTPStatusError as e:
            raise DiscoveryCreationError(
                f"Error creating discovery: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise DiscoveryCreationError(f"Error creating discovery: {e!r}") from e

    def get_discovery(self, discovery_id: UUID) -> DiscoveryResponse:
        """Get a discovery by its ID.

        Args:
            discovery_id: The ID of the discovery to get.

        Returns:
            The discovery.

        Raises:
            DiscoveryFetchError: If there's an error fetching the discovery.
        """
        try:
            response = self.client.get(f"/v0.1/discoveries/{discovery_id}")
            response.raise_for_status()
            return DiscoveryResponse.model_validate(response.json())
        except HTTPStatusError as e:
            raise DiscoveryFetchError(
                f"Error fetching discovery: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise DiscoveryFetchError(f"Error fetching discovery: {e!r}") from e

    def list_discoveries_for_project(
        self, project_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[DiscoveryResponse]:
        """List discoveries for a specific project.

        Args:
            project_id: The ID of the project to get discoveries for.
            limit: The maximum number of discoveries to return.
            offset: The number of discoveries to skip.

        Returns:
            A list of discoveries for the specified project.

        Raises:
            DiscoveryFetchError: If there's an error fetching the discoveries.
        """
        try:
            response = self.client.get(
                f"/v0.1/projects/{project_id}/discoveries",
                params={"limit": limit, "offset": offset},
            )
            response.raise_for_status()
            data = response.json()
            return [DiscoveryResponse.model_validate(d) for d in data]
        except HTTPStatusError as e:
            raise DiscoveryFetchError(
                f"Error fetching discoveries for project: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise DiscoveryFetchError(
                f"Error fetching discoveries for project: {e!r}"
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def create_job_event(
        self, request: JobEventCreateRequest
    ) -> JobEventCreateResponse:
        """Create a new job event.

        Args:
            request: Job event creation request

        Returns:
            Job event creation response

        Raises:
            JobEventCreationError: If the API call fails
        """
        try:
            response = self.client.post(
                "/v0.1/job-events",
                json=request.model_dump(exclude_none=True, mode="json"),
            )
            response.raise_for_status()
            return JobEventCreateResponse(**response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.BAD_REQUEST:
                raise JobEventCreationError(
                    f"Invalid job event creation request: {e.response.text}."
                ) from e
            if e.response.status_code == codes.NOT_FOUND:
                raise JobEventCreationError(
                    f"Execution not found for job event creation: {e.response.text}."
                ) from e
            raise JobEventCreationError(
                f"Error creating job event: {e.response.status_code} - {e.response.text}."
            ) from e
        except Exception as e:
            raise JobEventCreationError(
                f"An unexpected error occurred during job event creation: {e!r}."
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def acreate_job_event(
        self, request: JobEventCreateRequest
    ) -> JobEventCreateResponse:
        """Asynchronously create a new job event.

        Args:
            request: Job event creation request

        Returns:
            Job event creation response

        Raises:
            JobEventCreationError: If the API call fails
        """
        try:
            response = await self.async_client.post(
                "/v0.1/job-events",
                json=request.model_dump(exclude_none=True, mode="json"),
            )
            response.raise_for_status()
            return JobEventCreateResponse(**response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.BAD_REQUEST:
                raise JobEventCreationError(
                    f"Invalid job event creation request: {e.response.text}."
                ) from e
            if e.response.status_code == codes.NOT_FOUND:
                raise JobEventCreationError(
                    f"Execution not found for job event creation: {e.response.text}."
                ) from e
            raise JobEventCreationError(
                f"Error creating job event: {e.response.status_code} - {e.response.text}."
            ) from e
        except Exception as e:
            raise JobEventCreationError(
                f"An unexpected error occurred during job event creation: {e!r}."
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def update_job_event(
        self, job_event_id: UUID, request: JobEventUpdateRequest
    ) -> None:
        """Update an existing job event.

        Args:
            job_event_id: ID of the job event to update
            request: Job event update request

        Raises:
            JobEventUpdateError: If the API call fails
        """
        try:
            response = self.client.patch(
                f"/v0.1/job-events/{job_event_id}",
                json=request.model_dump(exclude_none=True, mode="json"),
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise JobEventUpdateError(
                    f"Job event with ID {job_event_id} not found."
                ) from e
            if e.response.status_code == codes.BAD_REQUEST:
                raise JobEventUpdateError(
                    f"Invalid job event update request: {e.response.text}."
                ) from e
            raise JobEventUpdateError(
                f"Error updating job event: {e.response.status_code} - {e.response.text}."
            ) from e
        except Exception as e:
            raise JobEventUpdateError(
                f"An unexpected error occurred during job event update: {e!r}."
            ) from e

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, max=MAX_RETRY_WAIT),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def aupdate_job_event(
        self, job_event_id: UUID, request: JobEventUpdateRequest
    ) -> None:
        """Asynchronously update an existing job event.

        Args:
            job_event_id: ID of the job event to update
            request: Job event update request

        Raises:
            JobEventUpdateError: If the API call fails
        """
        try:
            response = await self.async_client.patch(
                f"/v0.1/job-events/{job_event_id}",
                json=request.model_dump(exclude_none=True, mode="json"),
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            if e.response.status_code == codes.NOT_FOUND:
                raise JobEventUpdateError(
                    f"Job event with ID {job_event_id} not found."
                ) from e
            if e.response.status_code == codes.BAD_REQUEST:
                raise JobEventUpdateError(
                    f"Invalid job event update request: {e.response.text}."
                ) from e
            raise JobEventUpdateError(
                f"Error updating job event: {e.response.status_code} - {e.response.text}."
            ) from e
        except Exception as e:
            raise JobEventUpdateError(
                f"An unexpected error occurred during job event update: {e!r}."
            ) from e

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        retry=retry_if_connection_error,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def acreate_job_events_batch(
        self, request: JobEventBatchCreateRequest
    ) -> JobEventBatchCreateResponse:
        """Asynchronously create multiple job events in a single batch operation.

        Args:
            request: Batch job event creation request

        Returns:
            Job event batch creation response

        Raises:
            JobEventBatchCreationError: If the API call fails
        """
        try:
            response = await self.async_client.post(
                "/v0.1/job-events/batch",
                json=request.model_dump(exclude_none=True, mode="json"),
            )
            response.raise_for_status()
            return JobEventBatchCreateResponse(**response.json())
        except HTTPStatusError as e:
            if e.response.status_code == codes.BAD_REQUEST:
                raise JobEventBatchCreationError(
                    f"Invalid batch job event creation request: {e.response.text}."
                ) from e
            if e.response.status_code == codes.NOT_FOUND:
                raise JobEventBatchCreationError(
                    f"Execution not found for batch job event creation: {e.response.text}."
                ) from e
            raise JobEventBatchCreationError(
                f"Error creating batch job events: {e.response.status_code} - {e.response.text}."
            ) from e
        except Exception as e:
            raise JobEventBatchCreationError(
                f"An unexpected error occurred during batch job event creation: {e!r}."
            ) from e


def get_installed_packages() -> dict[str, str]:
    """Returns a dictionary of installed packages and their versions."""
    return {
        dist.metadata["Name"].lower(): dist.version
        for dist in importlib.metadata.distributions()
    }


def get_global_imports(global_scope: dict) -> dict[str, str]:
    """Retrieve global imports from the global scope, mapping aliases to full module names."""
    return {
        name: obj.__name__
        for name, obj in global_scope.items()
        if isinstance(obj, ModuleType)
    }


def get_referenced_globals_from_source(source_code: str) -> set[str]:
    """Extract globally referenced symbols from the source code."""
    parsed = ast.parse(source_code)
    return {
        node.id
        for node in ast.walk(parsed)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


def get_used_global_imports(
    func,
    global_imports: dict[str, str],
    global_scope: dict,
    visited=None,
) -> set[str]:
    """Retrieve global imports used by a function."""
    if visited is None:
        visited = set()
    if func in visited:
        return set()
    visited.add(func)
    used_imports: set[str] = set()
    source_code = inspect.getsource(func)
    referenced_globals = get_referenced_globals_from_source(source_code)
    used_imports.update(
        global_imports[name] for name in referenced_globals if name in global_imports
    )
    parsed = ast.parse(source_code)
    for node in ast.walk(parsed):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            ref_func = global_scope.get(node.func.id)
            if callable(ref_func):
                used_imports.update(
                    get_used_global_imports(
                        ref_func,
                        global_imports,
                        global_scope,
                        visited,
                    ),
                )
    return used_imports


def get_used_modules(env_builder: EnvironmentBuilder, global_scope: dict) -> set[str]:
    """Retrieve globally imported modules referenced by the start_fn and tools."""
    if not isinstance(env_builder, EnvironmentBuilder):
        raise TypeError("The provided object is not an instance of EnvironmentBuilder.")
    global_imports = get_global_imports(global_scope)
    used_imports = get_used_global_imports(
        env_builder.start_fn,
        global_imports,
        global_scope,
    )
    for tool in env_builder.tools:
        used_imports.update(
            get_used_global_imports(tool._tool_fn, global_imports, global_scope),
        )
    return used_imports


def generate_requirements(
    env_builder: EnvironmentBuilder,
    global_scope: dict,
) -> list[str]:
    """Generates a list of modules to install based on loaded modules."""
    used_modules = get_used_modules(env_builder, global_scope)
    used_modules.add("cloudpickle")
    installed_packages = get_installed_packages()
    pip_modules = {module for module in used_modules if module in installed_packages}
    return [f"{module}=={installed_packages[module]}" for module in sorted(pip_modules)]
