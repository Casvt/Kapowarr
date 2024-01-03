# Rate limiting

This page covers how Kapowarr handles the rate limits of the services it uses.

## ComicVine

Hourly, Kapowarr finds the volumes that haven't had a metadata fetch for more than a day. It tries to fetch for as many volumes as possible. If it can't fetch for them all in one go, the ones that didn't get fetched, get preference the next hour.

With this setup, all volumes (unless you have an absurdly big library) get updated every day and as little as possible requests are made. When we still surpass the limit, the volumes that need to be fetched the most (the ones that haven't been updated for the longest) get preference to ensure that they "keep up". Kapowarr can update at most 25.000 volumes and 25.000 issues per hour.

## Mega

If a Mega download reaches the rate limit of the account mid-download (no way to calculate this beforehand), the download is canceled and all other Mega downloads in the download queue are removed. From that point on, Mega downloads are skipped until we can download from it again. Alternative services like MediaFire and GetComics are used instead of Mega while we wait for the limit to go down again. If you have a Mega account that offers higher limits, it's advised to add it at Settings -> Download -> Credentials, so that Kapowarr can take advantage of it.
