## Download Location

### Direct Download Temporary Folder

This is where the files being downloaded get written to before being processed and moved to the correct location.

If you run Kapowarr using Docker, leave this set to the default value of `/app/temp_downloads` and instead change the value of `/path/to/download_folder` in the [Docker command](../installation/docker.md#launch-container). If you have a manual install, you can change this value to whatever you want. It is recommended to be outside your root folders.

### Empty Temporary Download Folder

This isn't so much of a setting as it is a tool. It will delete all files from the download folder that aren't actively being downloaded. This can be handy if the application crashed while downloading, leading to half-downloaded 'ghost' files in the folder.  

## Completed Download Handling

### Seeding Handling

When a torrent has completed downloading, it will start to seed depending on the settings of the torrent client. The originally downloaded files need to be available in order to seed. But you might not want to wait for the torrent to complete seeding before you can read the downloaded comics. Kapowarr offers two solutions:

1. **Complete**: wait until the torrent has completed seeding and then move the files. You'll have to wait until the torrent has completed seeding before the comics are available.
2. **Copy**: make a copy of the downloaded files and post-process those (moving, renaming, converting, etc.). When the torrent finishes seeding, it's files are deleted. With this setup, your downloaded comics will be available immediately, but will temporarily take up twice as much space.

### Delete Completed Torrents

If Kapowarr should delete torrents from the client once they have completed. Otherwise leave them in the queue of the torrent client as 'completed'.

## Service preference

Kapowarr has the ability to download directly from the servers of GetComics, but also to download from services like MediaFire and Mega. When an issue is queried on [GetComics](https://getcomics.org/) and found to have multiple possible download sources, this defines which source takes priority. If the first download fails, Kapowarr will try the next service in order.

If you have an account for one of these services (see [Credentials](#credentials) setting), you might want to put that one at the top, to make Kapowarr take advantage of the extra features that the account offers (extra bandwidth, higher rate limit, etc.).  
Options are:

- Mega
- MediaFire
- GetComics ("Main Server", "Mirror Server", etc.)
- GetComics (torrent)

## Credentials

If you have a paid account with Mega, Kapowarr has the ability to use this account. If you provide your login credentials for the service, Kapowarr will then take advantage of the extra features that your account has access to (higher speeds and limits, usually).  
