# How Sources with APIs Are Handled

## Overview

When a research source has an API available, ORKASTRATOR integrates it directly into the evidence search system. This document explains what happens when you use sources with APIs.

---

## API Integration Flow

### 1. **API Detection & Initialization**

When the system starts, it initializes API clients for each source:

```python
# In research_apis.py
class ResearchAPIManager:
    def __init__(self):
        self.arxiv = ArxivAPI()                    # No API key needed
        self.semantic_scholar = SemanticScholarAPI()  # Optional API key
        self.cve = CVEAPI()                        # Optional API key
        self.digikey = DigiKeyAPI()                # Required API key
        self.ieee = IEEEAPI()                      # Required API key
        # ... etc
```

**Key Points:**
- Some APIs work without keys (arXiv, USPTO via PatentsView)
- Some APIs work better with keys (Semantic Scholar, CVE/NVD)
- Some APIs require keys (Digi-Key, IEEE, EPO)

---

## What Happens When You Search

### Step 1: Query Processing

When you submit a search query:

```python
# User searches: "neural network optimization"
# System automatically detects relevant sources
api_sources = ['arxiv', 'semantic_scholar', 'papers_with_code']
# Or user manually selects sources via checkboxes
```

### Step 2: Parallel API Calls

The system makes **parallel HTTP requests** to each selected API:

```python
# All APIs are queried simultaneously
if 'arxiv' in sources:
    arxiv_results = self.arxiv.search(query, limit=5)
    
if 'semantic_scholar' in sources:
    scholar_results = self.semantic_scholar.search(query, limit=5)
    
if 'cve' in sources:
    cve_results = self.cve.search(query, limit=5)
```

### Step 3: Result Processing

Each API returns structured data:

```python
# Example: arXiv API returns
{
    'title': 'Neural Network Optimization',
    'authors': ['Smith, J.', 'Doe, A.'],
    'summary': 'Abstract text...',
    'published': '2024-01-15',
    'pdf_url': 'https://arxiv.org/pdf/...',
    'source': 'arXiv'
}

# Example: CVE API returns
{
    'id': 'CVE-2024-1234',
    'description': 'Vulnerability description...',
    'severity': 'HIGH',
    'published': '2024-01-10',
    'source': 'NVD/CVE'
}
```

---

## API Key Handling

### Three Categories of APIs

#### 1. **No API Key Required** ✅
- **arXiv**: Public API, no authentication
- **USPTO**: Public PatentsView API
- **Google Patents**: Public via PatentsView
- **IETF**: Public Datatracker API

**What Happens:**
```python
# API works immediately
results = arxiv_api.search("query")
# Returns results or empty list on error
```

#### 2. **Optional API Key** ⚠️
- **Semantic Scholar**: Works without key, but better with key
- **CVE/NVD**: Works without key, but rate-limited with key
- **WIPO**: Works without key, optional for higher limits

**What Happens:**
```python
# Checks for API key in environment
api_key = os.environ.get('SEMANTIC_SCHOLAR_API_KEY')

if api_key:
    headers['x-api-key'] = api_key  # Better rate limits
else:
    # Still works, but may have rate limits
    pass
```

**Behavior:**
- ✅ Works without key (may have rate limits)
- ✅ Works better with key (higher limits, faster)
- ⚠️ Logs warning if key would help but isn't set

#### 3. **Required API Key** 🔑
- **Digi-Key**: Requires API key
- **IEEE Xplore**: Requires subscription + API key
- **EPO**: Requires API key for full access
- **Octopart**: Requires API key

**What Happens:**
```python
def search(self, query: str, limit: int = 10):
    if not self.api_key:
        logger.warning("Digi-Key API key not configured")
        return []  # Returns empty, doesn't crash
    
    # Proceeds with API call if key exists
```

**Behavior:**
- ❌ Returns empty results if no key
- ⚠️ Logs warning message
- ✅ Works normally if key is set
- 🔄 System continues with other sources

---

## Error Handling

### Graceful Degradation

The system is designed to **never crash** if an API fails:

```python
try:
    results = api.search(query)
    return results
except ImportError:
    logger.warning("Package not installed")
    return []  # Empty list, not an error
except Exception as e:
    logger.error(f"API search error: {e}")
    return []  # Empty list, system continues
```

### What Happens on Errors

1. **API Timeout**: Returns empty results, logs warning
2. **API Key Missing**: Returns empty results, logs warning
3. **Network Error**: Returns empty results, logs error
4. **Invalid Response**: Returns empty results, logs error
5. **Rate Limit**: Returns empty results, logs warning

**Key Point**: The system **always continues** - if one API fails, others still work.

---

## Result Integration

### Step 1: Formatting for PaperQA

API results are converted to text documents:

```python
def format_for_paperqa(self, results):
    formatted = []
    for result in results:
        doc_parts = []
        doc_parts.append(f"Title: {result['title']}")
        doc_parts.append(f"Authors: {', '.join(result['authors'])}")
        doc_parts.append(f"Abstract: {result['abstract']}")
        doc_parts.append(f"Source: {result['source']}")
        formatted.append('\n\n'.join(doc_parts))
    return formatted
```

**Example Output:**
```
Title: Neural Network Optimization Techniques
Authors: Smith, J., Doe, A.
Abstract: This paper presents novel optimization methods...
Source: arXiv
```

### Step 2: Adding to PaperQA

Formatted documents are added to PaperQA's knowledge base:

```python
async def add_to_paperqa(self, docs, query, sources):
    # Search all APIs
    results = self.search_all(query, sources=sources)
    
    # Format results
    formatted_docs = self.format_for_paperqa(results)
    
    # Create temporary files
    for doc_text in formatted_docs:
        temp_file = temp_dir / f"research_{i}.txt"
        temp_file.write_text(doc_text)
        
        # Add to PaperQA
        await docs.aadd(str(temp_file))
```

### Step 3: Semantic Search

PaperQA then searches across:
- ✅ Local system documentation
- ✅ API results (from all selected sources)
- ✅ Previously indexed documents

All sources are searched **together** using semantic search.

---

## Real-World Example

### Scenario: Search "transformer architecture"

**User Query:**
```
"What are the latest transformer architectures?"
```

**System Behavior:**

1. **Auto-Detection:**
   ```python
   # Detects: academic query
   api_sources = ['arxiv', 'semantic_scholar', 'papers_with_code']
   ```

2. **Parallel API Calls:**
   ```
   arXiv API → Returns 5 papers
   Semantic Scholar API → Returns 5 papers (with API key)
   Papers with Code API → Returns 5 implementations
   ```

3. **Result Formatting:**
   ```
   Creates 15 formatted documents
   Each with title, authors, abstract, source
   ```

4. **PaperQA Integration:**
   ```
   Adds all 15 documents to search index
   Searches semantically across all sources
   Returns ranked results with citations
   ```

5. **User Gets:**
   ```json
   {
     "answer": "The latest transformer architectures include...",
     "sources": [
       {
         "name": "arxiv_paper_1.txt",
         "text": "Title: Transformer Architecture...",
         "score": 0.95
       },
       {
         "name": "semantic_scholar_paper_2.txt",
         "text": "Title: Advanced Transformers...",
         "score": 0.89
       }
     ]
   }
   ```

---

## API Key Configuration

### Setting API Keys

**Environment Variables:**
```bash
export SEMANTIC_SCHOLAR_API_KEY="your-key-here"
export NVD_API_KEY="your-key-here"
export DIGIKEY_API_KEY="your-key-here"
export IEEE_API_KEY="your-key-here"
export EPO_API_KEY="your-key-here"
export WIPO_API_KEY="your-key-here"
```

**In Code:**
```python
# Keys are automatically read from environment
api_key = os.environ.get('SEMANTIC_SCHOLAR_API_KEY')
```

### Getting API Keys

| Source | How to Get Key | Required? |
|--------|---------------|-----------|
| arXiv | None needed | ❌ No |
| Semantic Scholar | https://www.semanticscholar.org/product/api | ⚠️ Optional |
| CVE/NVD | https://nvd.nist.gov/developers/request-an-api-key | ⚠️ Optional |
| Digi-Key | https://developer.digikey.com | ✅ Yes |
| IEEE | Subscription required | ✅ Yes |
| EPO | https://developers.epo.org | ✅ Yes |
| WIPO | https://patentscope.wipo.int | ⚠️ Optional |
| USPTO | None needed (PatentsView) | ❌ No |

---

## Benefits of API Integration

### 1. **Real-Time Data**
- ✅ Always up-to-date results
- ✅ No manual data collection
- ✅ Automatic synchronization

### 2. **Structured Data**
- ✅ Consistent format
- ✅ Rich metadata (authors, dates, citations)
- ✅ Easy to process

### 3. **Scalability**
- ✅ Can query millions of records
- ✅ Parallel processing
- ✅ Efficient rate limiting

### 4. **Reliability**
- ✅ Graceful error handling
- ✅ Fallback mechanisms
- ✅ No single point of failure

---

## Comparison: With vs Without API

### Source WITH API ✅

**Advantages:**
- Real-time data access
- Structured, consistent format
- Can query millions of records
- Automatic updates
- Programmatic access
- Parallel queries possible

**Example:**
```python
# arXiv API - instant results
results = arxiv_api.search("neural networks")
# Returns: 10 papers in < 1 second
```

### Source WITHOUT API ❌

**Limitations:**
- Manual data collection required
- Static snapshots
- Limited to what's manually added
- No real-time updates
- Requires web scraping (fragile)

**Example:**
```python
# Manual collection - slow and limited
# Would need to:
# 1. Scrape website (fragile)
# 2. Parse HTML (error-prone)
# 3. Store manually (outdated quickly)
```

---

## Summary

**When a source has an API:**

1. ✅ **System queries it automatically** when selected
2. ✅ **Returns structured results** in consistent format
3. ✅ **Handles errors gracefully** (returns empty list, doesn't crash)
4. ✅ **Integrates with PaperQA** for semantic search
5. ✅ **Works with or without API keys** (depending on source)
6. ✅ **Continues if one API fails** (other sources still work)
7. ✅ **Provides real-time data** from live databases

**The system is designed to be resilient:**
- If an API is unavailable → other sources still work
- If an API key is missing → logs warning, continues
- If an API times out → returns empty, doesn't block
- If an API returns errors → handles gracefully

**Result:** You get comprehensive, real-time research results from multiple sources, even if some APIs are unavailable or misconfigured.

