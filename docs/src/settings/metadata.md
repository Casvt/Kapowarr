## Fetching

### Date Type

The type of release date that should be fetched for issues. Either the cover date or in-store date.

## Exporting

Kapowarr can export the metadata of issues as a `ComicInfo.xml` file into comic archives (CBZ, ZIP, CBR and RAR). Readers such as Komga and Kavita use it to match files and to show details.

### Export Metadata

Automatically export metadata after a file is downloaded. The file always gets the title, issue number, issue title, release date, publisher, format (TPB, one-shot, etc.), description, and the link to and ID of the issue at the metadata source.

Files that you already have can be exported with the 'Export Metadata' button when viewing a volume, which replaces any existing `ComicInfo.xml`, or with the Export Metadata action in the mass editor. The mass editor has a choice between:

| Choice | Result |
| ------ | ------ |
| Skip Existing | Files that already have a `ComicInfo.xml` are skipped |
| Force Overwrite | The `ComicInfo.xml` of every file is replaced |

_Note: the link to the issue is stored when the volume is refreshed. For volumes that were added before this was supported, do a Refresh & Scan before exporting to ensure the link is not left out._

### Export Extended Metadata

Also export the writers, artists, letterers, colorists, editors, characters, teams, locations and story arcs. This metadata is not stored internally by Kapowarr, but fetched on demand from the metadata source for each issue that is exported. Rate limits apply, so a limited amount of issues can receive extended metadata at a time.

If the limit is reached while exporting many files, Kapowarr safely stops and the status tab shows that the rate limit for fetching extended issue metadata has been reached. Similarly, for downloads that finish while the limit is reached, they are left without a metadata file until manually exported. In both cases, after the limit has reset, run the mass editor again with 'Skip Existing'.

Files that were exported when this setting was disabled are not updated automatically. Use 'Force Overwrite' to add the extended metadata to them.