After installing Kapowarr, you should have access to the web-ui. If not, check the [FAQ on this topic](../other_docs/faq.md#how-do-i-access-the-web-ui). Kapowarr needs some configuration in order for it to work properly.

## Port

The first thing to do is decide if you want to leave Kapowarr on the default port of 5656. If you want to _keep_ the port, you can go to the next step. If you want to _change_ the port, see the ['Port Number' setting](../settings/general.md#port-number).

## Authentication

If you want to put a password on your instance of Kapowarr, see the ['Login Password' setting](../settings/general.md#login-password).

!!! warning "Exposing Kapowarr"
	If you are exposing your Kapowarr instance to the internet, we highly recommend setting a password.

## ComicVine API key

Kapowarr uses [ComicVine](https://comicvine.gamespot.com/) as it's metadata source. To fetch the metadata from ComicVine, Kapowarr needs access to it's API, which requires an API key.

See the ['Comic Vine API Key' setting](../settings/general.md#comic-vine-api-key) for how to get one. Once you've entered your key and hit 'Save', move on to Root Folders.  

## Root folders

Root folders are the base folders that Kapowarr works in. All content is put in these folders. See the ['Root Folders' section of the settings](../settings/mediamanagement.md#root-folders) for more details.

!!! info "You need at least one root folder"
	At least one root folder must be set before you are able to add any volumes to your library.

## Direct Download Temporary Folder

If you want to, you can change the folder that Kapowarr downloads files to. It's called the ['Direct Download Temporary Folder' setting](../settings/download.md#direct-download-temporary-folder).

## Service preference

If you have an account with Mega, set that service as the priority and add a credential for it. The other services will then be used as a fallback option for if a link fails.

For a full explanation, see the ['Service Preference' section of the settings](../settings/download.md#service-preference).  

## Credentials

This only applies if you have an account with Mega (for now). Kapowarr can take advantage of the higher limits (download speed, daily size limit, etc.) that an account has to offer.

See the ['Credentials' section of the settings](../settings/download.md#credentials) for more info.

## Building a library

Now that you are ready, you can start [adding volumes to your library](../general_info/managing_volume.md#adding-volumes-to-your-library). If you have an existing library that you want to import into Kapowarr, use the [Library Import](../general_info/features.md#library-import) feature found at Volumes -> Library Import.
