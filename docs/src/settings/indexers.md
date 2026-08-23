This settings page allows you to manage your download indexers. Aside from the standard options, there are options that are specific to certain types of indexers. These are listed below.

## GetComics

### Avoid Large Downloads

GetComics offers downloads directly from their servers, but throttles the download speed significantly after downloading the first 400MB of a file. If the file is smaller than 400MB, then the download speed is never throttled. When this option is enabled, then if a file is larger than 400MB, try all external services (like Mega, MediaFire, etc.) first before resorting to downloading directly from the servers of GetComics.

### Service Preference

GetComics not only offers downloads directly from their servers, but also via services like Mega and MediaFire. When a download on GetComics is found and has multiple possible download services, this defines which service takes priority. If the first download fails, Kapowarr will try the next service in order.

If you have an account for one of these services (see [Credentials](./downloadclients.md#credentials) setting), you might want to put that one at the top, to make Kapowarr take advantage of the extra features that the account offers (extra bandwidth, higher rate limit, etc.).  
