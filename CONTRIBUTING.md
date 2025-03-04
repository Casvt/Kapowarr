# Contributing to Kapowarr
## General steps
Contributing to Kapowarr consists of 5 steps, listed hereunder. 

1. Make a [contributing request](https://github.com/Casvt/Kapowarr/issues/new?template=contribute_request.md), where you describe what you plan on doing. _This request needs to get approved before you can start._ The contributing request has multiple uses:
    1. Avoid multiple people working on the same thing.
    2. Avoid you wasting your time on changes that we do not wish for.
    3. If needed, have discussions about how something will be implemented.
    4. A place for contact, be it questions, status updates or something else.
2. When the request is accepted, start your local development (more info on this below).
3. When done, create a pull request to the development branch, where you quickly mention what has changed and give a link to the original contributing request issue.
4. The PR will be reviewed. Changes might need to be made in order for it to be merged. 
5. When everything is okay, the PR will be accepted and you'll be done!

## Local development

Once your contribution request has been accepted, you can start your local development. 

### IDE

It's up to you how you make the changes, but we use Visual Studio Code as the IDE. A workspace settings file is included that takes care of some styling, testing and formatting of the backend code.

1. The vs code extension `ms-python.vscode-pylance` in combination with the settings file with enable type checking.
2. The vs code extension `ms-python.mypy-type-checker` in combination with the settings file will enable mypy checking.
3. The vs code extension `ms-python.autopep8` in combination with the settings file will format code on save.
4. The vs code extension `ms-python.isort` in combination with the settings file will sort the import statements on save.
5. The settings file sets up the testing suite in VS Code such that you can just click the test button to run all tests.

If you do not use VS Code with the mentioned extensions, then below are some commands that you can manually run in the base directory to achieve similar results.

1. **Mypy**:
```bash
mypy --explicit-package-bases .
```
2. **autopep8**:
```bash
autopep8 --recursive --in-place .
```
3. **isort**:
```bash
isort .
```
4. **unittest**
```bash
python3 -m unittest discover -s ./tests -p '*.py'
```

### Strict rules

There are a few conditions that should always be met:

1. Kapowarr should support Python version 3.8 and higher.
2. Kapowarr should be compatible with Linux, MacOS, Windows and the Docker container.
3. The tests should all pass.

### Styling guide

Following the styling guide for the backend code is not a strict rule, but effort should be put in to conform to it as much as possible. Running autopep8 and isort handles most of this.

1. Indentation is done with 4 spaces. Not using tabs.
2. Use type hints as much as possible. If you encounter an import loop because something needs to be imported for type hinting, utilise [`typing.TYPE_CHECKING`](https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING).
3. A function in the backend needs a doc string describing the function, what the inputs are, what errors could be raised from within the function and what the output is.
4. The imports need to be sorted.
5. The code should, though not strictly enforced, reasonably comply with the rule of 80 characters per line.

## A few miscellaneous notes

1. Kapowarr does not have many tests. They're not really required if you checked your changes for bugs already. But you are free to add tests for your changes anyway.
2. The function [`backend.base.file_extraction.extract_filename_data`](https://github.com/Casvt/Kapowarr/blob/eadc04d10b32c04d4bbc51d289d10cfa93bc44f6/backend/base/file_extraction.py#L186) and [the regexes defined at the top](https://github.com/Casvt/Kapowarr/blob/development/backend/base/file_extraction.py#L24-L55) that it uses have become a bit of a box of black magic. If the function does not work as expected, it might be best to just inform @Casvt in the contribution request issue and he'll try to fix it.
