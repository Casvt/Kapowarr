## Built-in Clients

A list of the download clients Kapowarr has built-in. It uses these to download from multiple download services used by GetComics. Clicking on one of them shows a window with more information and, if the client has support for it, an option to enter credentials (see below).

### Credentials

If you have an account with Mega or Pixeldrain, Kapowarr has the ability to use this account. If you provide your login credentials for the service, Kapowarr will then take advantage of the extra features that your account has access to (higher speeds and limits, usually). You can enter the credentials by clicking on the client and filling in the form.

## External Download Clients

In order to download files through a more complicated protocol like torrent and usenet, add an external download client for that protocol. Kapowarr can then remotely control the client to download the files. Make sure that when you add an external download client for a specific protocol, that you also have added an [indexer](./indexers.md) that can find downloads utilising the protocol.

!!! warning "Using localhost in combination with a Docker container"
    If the external download client is hosted on the host OS, and Kapowarr is running inside a Docker container, then it is not possible to use `localhost` in the base URL of the client. Instead, the IP address used by the host OS must be used.

## Remote Path Mappings

When a remote download client and Kapowarr do not run on the same machine (because at least one of them is on another machine or in a Docker container), then filepaths could not match up. For example, a torrent client might be running in a Docker container where the download folder is at `/downloads` which maps to `/home/media/downloads` on the host while Kapowarr is running on the host. Then when Kapowarr reaches out to the torrent client, it'll report that the file is located at `/downloads/file.ext`. But Kapowarr can actually find it at `/home/media/downloads/file.ext`. 'Remote Path Mappings' allows you to add such a mapping so that Kapowarr can translate filepaths that are reported by the external download client to where it can actually find it.

When adding a remote mapping, choose the client it's for and then set the paths. The remote path is the path that the client reports (e.g. `/downloads`). The local path is the path that Kapowarr should actually look (e.g. `/home/media/downloads`).

!!! warning "Cross-OS remote mapping"
    Kapowarr currently does not support remote mappings between different operating systems. So for example, if a client is running on Windows and Kapowarr on Linux, then it currently doesn't support translating those. 
