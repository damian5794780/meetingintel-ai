import asyncio

from apps.api.services.provider_http import ProviderError, post_json
from apps.api.services.sources import canonical_url


class TavilyService:
    def __init__(self, settings, client, metrics):
        self.settings, self.client, self.metrics = settings, client, metrics

    async def search(self, queries, start, end):
        async def one(query):
            async def counted_post(*args, **kwargs):
                if self.metrics.search_calls >= 10:
                    raise ProviderError('Search request budget exhausted.')
                self.metrics.search_calls += 1
                return await self.client.post(*args, **kwargs)

            class CountedClient:
                post = staticmethod(counted_post)

            plan = query.model_dump() if hasattr(query, 'model_dump') else {'query': query, 'topic': 'news', 'domains': []}
            data = await post_json(CountedClient(), 'https://api.tavily.com/search',
                                   headers={'Authorization': f'Bearer {self.settings.tavily_key}'},
                                   json={'query': plan['query'], 'topic': plan['topic'], 'search_depth': 'advanced',
                                         'max_results': 5, 'start_date': start.date().isoformat(),
                                         'end_date': end.date().isoformat(), 'include_answer': False,
                                         'include_published_date': True, 'include_usage': True,
                                         'include_domains': plan['domains']})
            self.record_usage(data)
            rows = data.get('results')
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise ProviderError('Search provider returned an invalid result list.')
            return rows

        tasks = [asyncio.create_task(one(query)) for query in queries]
        try:
            results = await asyncio.gather(*tasks)
        except (Exception, asyncio.CancelledError):
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return [row for group in results for row in group]

    def record_usage(self, data):
        usage = data.get('usage') or {}
        credits = usage.get('credits')
        if isinstance(credits, (int, float)) and credits >= 0:
            self.metrics.tavily_credits += credits
        else:
            self.metrics.tavily_usage_complete = False

    async def extract(self, sources):
        urls = [s.url for s in sources if canonical_url(s.url)][:5]
        if not urls:
            return {}, []

        async def counted_post(*args, **kwargs):
            if self.metrics.extract_calls >= 4:
                raise ProviderError('Extraction request budget exhausted.')
            self.metrics.extract_calls += 1
            return await self.client.post(*args, **kwargs)

        class CountedClient:
            post = staticmethod(counted_post)

        data = await post_json(CountedClient(), 'https://api.tavily.com/extract',
                               headers={'Authorization': f'Bearer {self.settings.tavily_key}'},
                               json={'urls': urls, 'extract_depth': 'basic', 'format': 'markdown',
                                     'include_usage': True, 'timeout': 15})
        self.record_usage(data)
        results, failures = data.get('results'), data.get('failed_results', [])
        if not isinstance(results, list) or not isinstance(failures, list):
            raise ProviderError('Extraction provider returned invalid results.')
        allowed = set(urls)
        extracted = {}
        for row in results:
            if not isinstance(row, dict):
                continue
            url = canonical_url(str(row.get('url', '')))
            content = row.get('raw_content')
            if url in allowed and isinstance(content, str) and content.strip():
                extracted[url] = content.strip()[:12000]
        missing = len(allowed - set(extracted))
        warnings = [f'{missing} selected pages could not be extracted; their search snippets are labeled as fallback evidence.'] if missing else []
        return extracted, warnings
