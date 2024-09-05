## Built-in Clients

A list of the download clients Kapowarr has built-in. It uses these to download from multiple sources offered by GetComics. Clicking on one of them shows a window with more information and, if the client has support for it, an option to enter credentials (see below).

### Credentials

If you have an account with Mega, Kapowarr has the ability to use this account. If you provide your login credentials for the service, Kapowarr will then take advantage of the extra features that your account has access to (higher speeds and limits, usually). You can enter the credentials by clicking on the client and filling in the form.

## Torrent Clients

By adding at least one torrent client, Kapowarr is able to download torrents.

!!! warning "Using localhost in combination with a Docker container"
    If the torrent client is hosted on the host OS, and Kapowarr is running inside a Docker container, then it is not possible to use `localhost` in the base URL of the torrent client. Instead, the IP address used by the host OS must be used.
