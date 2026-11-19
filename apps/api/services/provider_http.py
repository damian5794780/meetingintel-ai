import asyncio

import httpx


class ProviderError(Exception):
    """Safe user-facing error: never include response bodies or credentials."""


async def post_json(client, url, **kwargs):
    for attempt in range(2):
        try:
            response = await client.post(url, **kwargs)
            if response.status_code in (401, 403):
                raise ProviderError('Provider rejected the API key. Check backend configuration.')
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 0:
                    await asyncio.sleep(0.4)
                    continue
                raise ProviderError('Provider is busy or quota is exhausted. Please try again later.')
            if not response.is_success:
                raise ProviderError('Provider rejected the request. Check the model and endpoint configuration.')
            return response.json()
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt == 1:
                raise ProviderError('Provider connection timed out or is unavailable.') from None
        except ValueError:
            raise ProviderError('Provider returned an unreadable response.') from None
    raise ProviderError('Provider unavailable.')
