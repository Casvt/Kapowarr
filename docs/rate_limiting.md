# Rate limiting
This page covers how Kapowarr handles with the rate limits of services it uses.

## ComicVine
Hourly, Kapowarr finds the volumes that haven't had a metadata fetch for more than a day. It tries to fetch for as many volumes as possible. If it can't fetch for them all in one go, the ones that didn't get fetched, get preference the next hour. For the fetched volumes, Kapowarr checks when the last time was that the metadata was updated and compares it to it's stored date. If it determines that the metadata for the volume has been updated since the last fetch, it applies the fetched metadata for the volume and fetches the metadata for all issues of the volume and apply that too.

With this setup, all volumes (unless you have an absurdly big library) get updated every day and as little as possible requests are made. When we still surpass the limit, the volumes that need to fetched the most (the ones that haven't been updated for the longest) get preference to ensure that they "keep up". With this setup, worst case scenario, 25.000 volumes and 25.000 issues can be updated per hour. However, because metadata of a volume doesn't get updated often, Kapowarr only needs to update a few volumes _per day_, assuming you have a library of a few thousand volumes.

## Mega
If a Mega download reaches the rate limit of the account mid-download (no way to calculate this beforehand), the download is canceled and all other Mega downloads in the download queue are removed. From that point on, Mega downloads are skipped until we can download from it again. Alternative services like MediaFire and GetComics are used instead of Mega while we wait for the limit to go down again. If you have a Mega account that offers higher limits, it's advised to add it at Settings -> Download -> Credentials, so that Kapowarr can take advantage of it.
