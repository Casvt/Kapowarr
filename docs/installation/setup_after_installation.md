After installing Kapowarr, you should have access to the web-ui. If not, check the [FAQ on this topic](../other_docs/faq.md#how-do-i-access-the-web-ui). Kapowarr needs some configuration in order for it to work properly. Remember that you should click 'Save' after changing settings.

## Authentication

If you want to require authentication when accessing Kapowarr, see the ['Authentication' setting](../settings/general.md#authentication).

!!! warning "Exposing Kapowarr"
	If you are exposing your Kapowarr instance to the internet, we highly recommend enabling authentication.

## ComicVine API key

Kapowarr uses [ComicVine](https://comicvine.gamespot.com/) as its metadata source. To fetch the metadata from ComicVine, Kapowarr needs access to its API. That requires a ComicVine API key. See the ['Comic Vine API Key' setting](../settings/general.md#comic-vine-api-key) for how to get one.

## Root folders

Root folders are the base folders that Kapowarr puts media files in. Add at least one root folder to be able to add any volumes to your library. See the ['Root Folders' section of the settings](../settings/mediamanagement.md#root-folders) for more details.

!!! warning "Adding root folders on Docker"
	If you use Docker to run Kapowarr, then the root folder that you enter in the web-UI is the mapped folder, not the folder path on the host machine. That means that if you followed the [Docker installation instructions](../installation/docker.md#launch-container), you would need to enter `/comics-1`, `/comics-2`, etc. as your root folder.

## Direct Download Temporary Folder

This is only applicable to people _not_ using Docker. If you want to, you can change the folder that Kapowarr downloads files to using the ['Direct Download Temporary Folder' setting](../settings/download.md#direct-download-temporary-folder).

## Credentials

If you have an account at a download service like Mega or Pixeldrain, then Kapowarr can take advantage of the higher limits (download speed, daily download limit, etc.) that the account has to offer. See the ['Credentials' section of the settings](../settings/downloadclients.md#credentials) for more details.

## Building a library

Now you can start filling up your library. You can [add volumes to your library](../general_info/how_to_use.md) or import an existing library of media files using [Library Import](../general_info/library_import.md).
