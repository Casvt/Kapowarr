# FAQ

## Project

### Does Kapowarr support XYZ?

Look around in the web-UI and this documentation hub first, to see if you find it. Otherwise you can ask on the [Discord server](https://discord.gg/nMNdgG7vsE). If you are sure that it is not available in Kapowarr, you can [report it](./reporting.md).

### When will XYZ be added?

First, check out the [project board](https://github.com/users/Casvt/projects/5) to see if it's already on there and if so, at what stage it is. If it's not, check if a feature request is already made for it on the [issues page](https://github.com/Casvt/Kapowarr/issues) and otherwise [make an issue yourself](./reporting.md).

### What are the alpha releases?

Sometimes, between stable releases, alpha releases are published. These releases contain new features/fixes that need to be tested before being published to the general public. So they contain the latest features and fixes, but possibly also bugs. Once any problems found in the alpha releases are fixed, the stable changes are released in a stable release. The alpha releases can be used by pulling the Docker image from the [`mrcas/kapowarr-alpha`](https://hub.docker.com/r/mrcas/kapowarr-alpha) repository. Any stable releases are also published in the alpha repository, so you do not have to switch to the stable repository in order to get the stable releases.

## Hosting

### Why is the binding address set to 0.0.0.0?

This is the default value, and will make Kapowarr bind to all interfaces it finds on the host machine. You can specify a specific IP address that the host machine owns to only bind to, but this is uncommon.

### How do I access the web-UI?

- **Localhost**  
    If you want to access the web-UI from the same computer that Kapowarr is running on, you can go to [http://localhost:5656](http://localhost:5656). This is assuming that Kapowarr is running on the default port of 5656.
- **IP**  
    You can access the web-UI from any computer that is on the same network by using the IP address of the computer that Kapowarr is running on. Then you can access it via `{IP}:5656`. So if the IP address is `192.168.2.15`, you can access the web-UI via `192.168.2.15:5656` or `http://192.168.2.15:5656`.
- **Hostname**  
    You can access the web-UI in the same way that you can access it using the IP address, but by using the hostname of the computer instead (if the compute has a hostname). For example, if your computer has the hostname `my-server`, then you can access the web--UI via `my-server:5656` or `http://my-server:5656`.

!!! tip "Check your firewall"
    If you can still not access the web-UI, check if the port is allowed through the firewall.

## Library Management

### Why can't I add volumes to my library?

The two most common causes for this are:

- Not having a valid [ComicVine API key](../settings/general.md#comic-vine-api-key) to be able to match or look up volumes.
- Not having a [root folder](../settings/mediamanagement.md#root-folders) defined.

## Matching

A lot of the problems with matching are caused by [the Special Version of the volume](../general_info/matching.md#special-version) not being determined correctly. This is the first thing that should be checked, in case of problems with matching.

### Why don't my files match to the volume?

There are multiple causes to this:

1. The files are not in the volume folder.

2. The files aren't for the volume:

!!! info "Kapowarr is right"
    If the volume in your library is for a TPB, and the files are for individual issues, then Kapowarr is correct in not matching the files. This often happens in the scenario where a TPB file is (incorrectly) named as "Issue 1". The same goes for Deluxe Editions: if the file is for a Deluxe Edition and the volume is for a standard version, then Kapowarr is correct in not matching the file. Almost always, the correct version of the volume can be added to your library, fixing the problem. With the example of the Deluxe Edition, you can fix it by adding the Deluxe Edition of the volume from ComicVine to your library.

!!! info "Kapowarr is wrong"
    <a name="wrong-special-version"></a> Kapowarr tries to automatically determine the [Special Version](../general_info/matching.md#special-version) of a volume, but it isn't always right. For example, it often marks One Shot's as TPB's. Read the linked section for more information on the Special Version of a volume. Editing the volume and overriding the Special Version often resolves problems. Please [report](./reporting.md) a volume if the Special Version was wrongly determined and you think Kapowarr could've done it correctly.

3. <a name="wrong-filename"></a> The filename does not follow the [matching criteria](../general_info/matching.md#files-to-issues). The filename does not have to be perfect, but it does have to give the correct information. For example, it often happens that TPB files have "Issue 1" in their filename, which does not meet [rule 2 of the matching criteria for TPB's](../general_info/matching.md#tpb-volume).

3. The filename is simply not handled properly by Kapowarr. The chance of this happening is slim, but if you think this is the case, please [report it](../other_docs/reporting.md).

### Why do files pop up in Library Import, even though I just imported them?

When you import a file, the matched volume is added to your library and the file is matched to one or more issues of the volume. However, the file failed to match to the volume. The file is not matched to anything, so it pops up in Library Import.

There are multiple causes to the file not matching to the volume:

1. In Library Import, the file was matched to the wrong volume. If the volume is not for the file, then the file won't match. Make sure the file is matched to the correct volume before importing. Check the "Issues in match" column in the Library Import result, which refers to how many issues the matched volumes contains, to quickly get an idea of the correctness of the match.

??? example "Examples"
    1. If you have 6 issues of a volume, but the "Issues in match" column says 4, then the match must be wrong.
    
    2. Sometimes a one shot file matches to the TPB instead (in the rare scenario where a volume has both a TPB and a one shot). Both volumes only have 1 issue, so both will have 1 as their "Issues in match" value. The only way to check if the match is correct is to click on the match, bringing you to the ComicVine page and checking yourself.

    3. Sometimes an annual matches to the volume referring to one a year earlier or later. Check the year of the matched volume in such scenarios. 

2. The file matched to the correct volume, but the [Special Version](../general_info/matching.md#special-version) of the volume was incorrectly determined, leading to a failure to match. This is now not a problem specific to Library Import anymore, and is covered in the section ["Why don't my files match to the volume?" -> Bullet 2 -> "Kapowarr is wrong"](#wrong-special-version).

3. The file matched to the correct volume, but is not named correctly, leading to a failure to match. This is not not a problem specific to Library Import anymore, and is covered in the sections ["Why don't my files match to the volume?" -> Bullet 3 & 4](#wrong-filename).

### Why does Kapowarr not grab the links from a GC page even though they work fine?

GetComics pages often contain downloads for more than what is needed, so Kapowarr filters the links based on what it needs and what it doesn't. If Kapowarr did not download anything from a GC page, then it thought the links weren't for any content of interest [that matches the criteria](../general_info/matching.md#getcomics-groups).

There are multiple causes to this:

1. Kapowarr wrongly thinks that the links do not lead to files that are of interest, because the [Special Version](../general_info/matching.md#special-version) of the volume was incorrectly determined. Edit the volume and override the Special Version, if it is not correct already. 

??? example "Example"
    Say there is a volume, that Kapowarr determines to be a one-shot. However, it is in fact a TPB. When Kapowarr goes searching, it looks for a one-shot download. It does not find any downloads for a one-shot, only TPB's. Thus it does not download anything. By overriding the Special Version of the volume to "Trade Paper Back", Kapowarr will now match to download links for TPB's and successfully download the media.

2. Kapowarr correctly thinks that the links do not lead to files that are of interest. For example, Kapowarr will not download a TPB, if the volume that is being searched for is a normal, non-TPB, volume. In this case Kapowarr is correct, and if the TPB is desired, that version of the volume should instead be added to your library.

3. Kapowarr wrongly thinks that the links do not lead to the files that are of interest, because the matching simply fails. For example, it might think 'Tom: His Perspective' and 'The Perspective of Tom' do not refer to the same volume, and thus reject it.

4. The service or service category that the link links to is not supported. For example, Kapowarr can download from Mega, but it can't download Google Drive folders.

If you still want to download the media, you can click the "Force Download" button in the Manual Search results to force Kapowarr to download all content from the page. No filtering will be done, and the downloaded files will be put in the volume folder, but they will not be renamed.
