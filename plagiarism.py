"""PlagiarismCheck.org single-account API adapter.

Contract: https://plagiarismcheck.org/for-developers/
No document is submitted until the authenticated user explicitly requests it.
"""
import math
import os
from urllib.parse import urlparse
import requests

PROVIDER = 'PlagiarismCheck.org'
MAX_CHARACTERS = 100_000


class PlagiarismError(Exception):
    pass


def configured():
    return bool(os.environ.get('PLAGIARISMCHECK_API_TOKEN', '').strip())


def _request(method, path, data=None):
    token = os.environ.get('PLAGIARISMCHECK_API_TOKEN', '').strip()
    if not token:
        raise PlagiarismError('Plagiarism checking is not configured. Set PLAGIARISMCHECK_API_TOKEN on the server.')
    try:
        response = requests.request(method, f'https://plagiarismcheck.org/api/v1/{path}',
                                    headers={'X-API-TOKEN': token}, data=data,
                                    timeout=(5, 30), allow_redirects=False)
        if response.status_code in (401, 403):
            raise PlagiarismError('The provider rejected the API token. Ask the administrator to check it.')
        if response.status_code == 402:
            raise PlagiarismError('The provider account needs credits before it can run this scan.')
        if response.status_code == 429:
            raise PlagiarismError('The provider is rate-limiting requests. Wait before checking again.')
        if not 200 <= response.status_code < 300:
            raise PlagiarismError('The plagiarism service could not complete this request.')
        result = response.json()
        if not isinstance(result, dict) or result.get('success') is False or not isinstance(result.get('data'), dict):
            raise PlagiarismError('The plagiarism service returned an invalid response.')
        return result['data']
    except (requests.RequestException, ValueError) as exc:
        raise PlagiarismError('Could not reach the plagiarism service or read its response. A submitted scan may still consume credits.') from exc


def submit(text):
    if not 80 <= len(text.strip()) <= MAX_CHARACTERS:
        raise PlagiarismError('Scan text must contain between 80 and 100,000 characters. No text was sent.')
    result = _request('POST', 'text', {'language': 'en', 'text': text})
    try:
        scan_id = int(result['text']['id'])
        if scan_id < 1:
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise PlagiarismError('The provider did not return a valid scan ID. Check the provider dashboard before submitting again.') from exc
    return scan_id


def _percent(value):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise ValueError('Invalid percentage')
    return number


def _safe_url(value):
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username else None


def status(scan_id):
    data = _request('GET', f'text/{int(scan_id)}')
    if data.get('state') in (2, 3):
        return {'status': 'pending', 'provider': PROVIDER}
    if data.get('state') == 4:
        return {'status': 'failed', 'provider': PROVIDER, 'message': 'The provider could not check this text. Review the scan in your provider account.'}
    if data.get('state') != 5:
        raise PlagiarismError('The provider returned an unknown scan status.')
    data = _request('GET', f'text/report/{int(scan_id)}')
    try:
        percent = _percent(data['report']['percent'])
        details = data['report_data']
        raw_sources = details['sources']
        if not isinstance(raw_sources, list) or not isinstance(details.get('nodes', []), list):
            raise ValueError()
        sources = []
        for index, source in enumerate(raw_sources[:100]):
            url = _safe_url(source.get('source'))
            if url:
                sources.append({'index': index, 'url': url, 'percent': _percent(source.get('percent', source.get('plagiarism_percent')))})
        matches = []
        for node in details.get('nodes', []):
            if node.get('enabled') and node.get('sources'):
                urls = [s['url'] for s in sources if s['index'] in node['sources']]
                matches.append({'text': str(node.get('text', ''))[:2000], 'sources': urls})
                if len(matches) == 20:
                    break
        return {'status': 'completed', 'provider': PROVIDER, 'similarity_percent': percent,
                'sources': sources, 'source_count': len(raw_sources), 'matches': matches,
                'note': 'Similarity is not proof of plagiarism. Review quotations, citations and source context. Up to 100 sources and 20 passage excerpts are shown.'}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise PlagiarismError('The provider report could not be read. No similarity score has been assumed.') from exc
