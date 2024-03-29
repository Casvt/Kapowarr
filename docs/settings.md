# Settings

This page will cover the Settings sections.  
Each setting type is grouped based on what they're related to.

## Media Management

Here is where you configure your settings related to how your media files are handled.

### File Naming

#### Rename Downloaded Files
When a file is downloaded, this setting decides if it should be renamed or not. If not, the default filename is used. If so, it is renamed following the formats set below.

#### Volume Folder Naming

The naming format for the volume folder (folder structure allowed).  
Available variables are:

- {series_name}
- {clean_series_name}
- {volume_number}
- {comicvine_id}
- {year}
- {publisher}

For example, `{series_name} ({year})` will come out as "Invincible Iron Man (2019)".

#### File Naming

The naming format for the file itself.  
Available variables are:

- {series_name}
- {clean_series_name}
- {volume_number}
- {comicvine_id}
- {year}
- {publisher}
- {issue_comicvine_id}
- {issue_number}
- {issue_title}
- {issue_release_date}
- {issue_release_year}

For example, `{series_name} ({year}) Volume {volume_number} Issue {issue_number} {issue_title}` would come out as "Invincible Iron Man (2008) Volume 01 Issue 001 The Five Nightmares Part 1 Armageddon Days.cbz".

#### File Naming For TPB

The naming format for the file itself (if it's a TPB).  
Available variables are:

- {series_name}
- {clean_series_name}
- {volume_number}
- {comicvine_id}
- {year}
- {publisher}

For example, `{series_name} ({year}) Volume {volume_number} TPB` would come out as "Invincible Iron Man (2019) Volume 01 TPB.cbz"

#### File Naming For Issues Without Title

The naming format for the file itself if there is no issue-specific title.

If the value of the setting [File Naming](#file-naming-1) uses the issue title, it will most likely look ugly when the issue doesn't have a title. For example, if your format is `Issue {issue_number} - {issue_title}`, but the issue doesn't have a title, it will result in a file like `Issue 5 - .cbr`. For that scenario, this setting exists. Here you can set an alternative format for when the issue doesn't have a title.

Available variables are:

- {series_name}
- {clean_series_name}
- {volume_number}
- {comicvine_id}
- {year}
- {publisher}
- {issue_comicvine_id}
- {issue_number}
- {issue_release_date}
- {issue_release_year}

For example, `{series_name} ({year}) Volume {volume_number} Issue {issue_number}` would come out as "Invincible Iron Man (2008) Volume 01 Issue 001.cbz".

#### Treat Volume Issues as "No Title"

Sometimes a volume will consist of multiple sub-volumes. This setting controls whether Kapowarr should name these the same as issues without a title or not. See the example below:

| Setting | Example Result |
| ------- | -------------- |
| Enabled | Invincible Compendium (2011) Volume 1 Issue 1-2.cbr<br>Invincible Compendium (2011) Volume 1 Issue 3.cbr |
| Disabled | Invincible Compendium (2011) Volume 1 - 2.cbr<br>Invincible Compendium (2011) Volume 3.cbr |

#### Issue Padding

This defines how issue numbers are 'padded' (3 digits, 2 digits, etc.).  
This is useful in the case of file sorting, as many operating systems sort _alphabetically_, instead of alphanumerically. To them, because 1 is lower than 2, "11" comes before "20".  
To get around this, we 'pad' the numbers with leading zeroes. "1" becomes"001", "11" becomes "011", and "2" becomes "002" - resulting in a more accurate sort.

Options are:

- x (no padding, i.e. 1,2,...10)
- 0x (2 digits, i.e. 01, 02...10)
- 00x (3 digits, i.e. 001, 002...010...099,100)

#### Volume Padding

This defines how volume numbers are 'padded' (3 digits, 2 digits, etc.).  
This is useful in the case of file sorting, as many operating systems sort _alphabetically_, instead of alphanumerically. To them, because 1 is lower than 2, "11" comes before "20".  
To get around this, we 'pad' the numbers with leading zeroes. "1" becomes"001", "11" becomes "011", and "2" becomes "002" - resulting in a more accurate sort.

Options are:

- x (no padding, i.e. 1,2,...10)
- 0x (2 digits, i.e. 01, 02...10)
- 00x (3 digits, i.e. 001, 002...,010...099,100)

### Converting

The "Converting" feature allows you to change the format of your files (e.g. from cbr to cbz). It can also extract archive files.

#### Covert Files

If Kapowarr should automatically convert files after they've been downloaded. Kapowarr will follow the format preference set.

#### Extract archives covering multiple issues

If an archive file is downloaded with multiple issues inside, then first extract the files inside and _then_ convert. With the setting disabled, Kapowarr will covert the file as normal. Even when no format preference is set (don't convert), this setting can still be enabled to extract archive files (up to beta-3, this was called 'unzipping').

#### Format Preference

The formats that Kapowarr should convert the files to. It will try to convert the files to the format at place 1, but if that is not possible, it will fallback to the format at place 2, and so forth. The last place will always be occupied by the format 'No Conversion'. That means that if Kapowarr is not able to convert the file to any of the set formats, it will just keep the current one. If no format preference is set ('No Conversion' is at place 1), no conversion will happen. The format 'folder' means extracting archive files. Kapowarr will extract all files inside the archive, delete the original archive file, filter unrelated files and rename the relevant ones.

_Note: if Kapowarr determines that a file in the archive file is not related to the volume, it will not be extracted and will be deleted when the archive file is finished being unpacked.
If you find faulty deletions occurring, please [lodge an issue](https://github.com/Casvt/Kapowarr/issues) for this._

### Root Folders

Root folders are the base folders that Kapowarr works in. All content is put in these folders.  

When adding a volume (or when editing one), you choose in which root folder all content for that volume is put. Kapowarr will never touch any files outside the root folders (except in the [download folder](#download-location)). You might have multiple root folders because you store your comics on multiple drives or want different access rights to certain volumes, to name a few reasons.

Root folders can be added at Settings -> Media Management -> Root Folders. Note: If you use docker to run Kapowarr and have followed the example given in the [installation instructions](./installation.md#docker), this is where you would enter `/comics-1`, `/comics-2`, `/RF`, `/RF2`, etc.

_Note: at least one of these must be set before you are able to add any volumes to monitor, as without it Kapowarr cannot know where to put the files._

## Download

### Download Location

#### Direct Download Temporary Folder

This is where the files being downloaded get written to before being processed and moved to the correct location.  
The default location for this is `/app/temp_downloads`.

If you run Kapowarr using Docker, leave this set to the default value of `/app/temp_downloads` and instead change the value of `/path/to/download_folder` in the Docker command ([reference](./installation.md#docker)).  
If you have a manual install, you can change this value to whatever you want. It is recommended to be outside your root folders.

#### Empty Temporary Download Folder

This isn't so much of a setting as it is a tool. It will delete all files from the download folder that aren't actively being downloaded. This can be handy if the application crashed while downloading, leading to half-downloaded files in the folder.  

### Completed Download Handling

#### Seeding Handling

When a torrent download is done, depending on the settings of the torrent client, it will start to seed. The originally downloaded files need to be available in order to seed. But you might not want to wait for the torrent to complete seeding before you can read the downloaded comics. Kapowarr offers two solutions:

1. 'Complete': wait until the torrent has completed seeding and then move the files. You'll have to wait until the torrent has completed seeding before the comics are available.
2. 'Copy': make a copy of the downloaded files and post-process those (moving, renaming, converting, etc.). When the torrent finishes seeding, it's files are deleted. With this setup, your downloaded comics will be available immediately, but will temporarily take up twice as much space.

#### Delete Completed Torrents

If Kapowarr should delete torrents from the client once they have completed. Otherwise leave them in the queue of the torrent client as 'completed'.

### Service preference

Kapowarr has the ability to download directly from the servers of GetComics, but also to download from services like MediaFire and Mega. When an issue is queried on [GetComics](https://getcomics.org/) and found to have multiple possible download sources, this defines which link takes priority.  

If the first download fails, Kapowarr will try the next service in order.  

If you have an account for one of these services (see [Credentials](#credentials) setting), you might want to put that one at the top, to make Kapowarr take advantage of the extra features that the account offers (extra bandwidth, higher rate limit, etc.).  
Options are:

- Mega
- MediaFire
- GetComics ("Main Server", "Mirror Server", etc.)

### Credentials

If you have a paid account with Mega, Kapowarr has the ability to use this account.  
If you provide your login credentials for the service, Kapowarr will then take advantage of the extra features that your account has access to (higher speeds and caps, usually).  

## Download Clients

On this page you can add external download clients. Currently, only torrent clients are supported, which can be used for downloading torrents that GetComics offers.

## General

### Host

This section defines how Kapowarr binds to a port/IP when starting up.  
Any setting here requires you restart Kapowarr after saving it for it to apply.

#### Bind Address

This tells Kapowarr what IP to bind to. If you specify an IP that is _not_ on the machine running Kapowarr, you _will_ encounter errors.  
Using `0.0.0.0` will have Kapowarr bind to all interfaces it finds on the host machine.

_Note: this setting is not applicable if you have Kapowarr deployed with Docker._

#### Port Number

This tells Kapowarr what port to listen on. The default is `5656`, which would put the Kapowarr UI on `http://ip.of.host.machine:5656/`.  
If you wish to change the port, it can be changed here.  
_Note: this setting is not applicable if you have Kapowarr deployed with Docker. This should be done by following the examples below_.

=== "Docker CLI"
    Alter the command to run the container and replace `-p 5656:5656` with `-p {PORT}:5656`, where `{PORT}` is the desired port (e.g. `-p 8009:5656`).  
    Run the container with the new version of the command (you will need to remove the old container if you had it running before).

=== "Docker Compose"
    Alter the file to run the container and replace `- 5656:5656` with `- {PORT}:5656`, where `{PORT}` is the desired port (e.g. `- 8009:5656`).  
    Then re-run the container with the new version of the file.

=== "Manual Install"
    Edit the port number here by changing the value to the desired port. Press save, then restart Kapowarr.

#### Base URL

This is use for reverse proxy support - the default is empty.  
If you want to put Kapowarr behind a proxy (so you can access via a nice URL), set a Base URL (it _must_ start with a `/` character).  

To get `http://example.com/kapowarr`, you would set your reverse proxy to forward the `/kapowarr` path to the IP and port of your Kapowarr instance, and set Base URL to `/kapowarr`.

### Security

#### Login Password

You might want to set a password to restrict access to the web-ui (and API). This is optional (but highly recommended if you are exposing Kapowarr to the internet).  
From then on, it is required to enter a password in order to gain access to the web-ui (and the API).  
If you want to disable the password, set an empty value for the setting and save.

#### API Key

This is where Kapowarr defines the API key for any queries made to the [Kapowarr API](api.md).  
Documentation for the API itself will be coming in due course.

### Comic Vine API Key

Kapowarr uses ComicVine as its metadata source. To fetch the metadata from ComicVine, Kapowarr needs access to the API, which requires an API key.

1. Go to [the API page of ComicVine](https://comicvine.gamespot.com/api/).
2. If you don't have a free account at ComicVine already, sign up and once logged in, revisit the linked page.
3. You'll see your ComicVine API key, which is 40 characters long and contains the letters a-f and numbers 0-9 (e.g. `da39a3ee5e6b4b0d3255bfef95601890afd80709`).
4. Copy that API key and enter it as the value of Settings -> General -> Comic Vine API -> Comic Vine API Key in the web-ui. Don't forget to save.

On the documentation page about [rate limiting](rate_limiting.md), information can be found about the handling of the ComicVine API rate limit.

### UI

#### Theme

The default theme is "Light". If you like dark mode, select "Dark".

### Logging

#### Log Level

The default log level is 'Info'. This means that only things that would appear in a console (or stdout) get logged.  
If troubleshooting, setting this to 'Debug' will make the system log what it's doing in much more detail.  

_Note that this should be set to 'Info' when not debugging, as the log files can start to get rather large._
