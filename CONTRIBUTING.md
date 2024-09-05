# Contributing to Kapowarr
## General steps
Contributing to Kapowarr consists of 5 steps, listed hereunder. 

1. Make a [contributing request](https://github.com/Casvt/Kapowarr/issues/new?template=contribute-request.md), where you describe what you plan on doing. This request needs to get approved before you can start, or your pull request won't be accepted. This is to avoid multiple people from doing the same thing and to avoid you wasting your time if we do not wish the changes. This is also where discussions can be held about how something will be implemented.
2. When the request is accepted, start your local development (more info about this below).
3. When done, create a pull request to the development branch, where you mention again what you've changed/added and give a link to the original contributing request issue.
4. The PR will be reviewed and if requested, changes will need to be made before it is accepted. 
5. When everything is okay, the PR will be accepted and you'll be done!

## Local development steps
Once your request is accepted, you can start your local development.

1. Clone the repository onto your computer and open it using your preferred IDE (Visual Studio Code is used by us).
2. Make the changes needed and write accompanying tests if needed.
3. Check if the code written follows the styling guide below.
4. Run the finished version, using python 3.8, to check if you've made any errors.
5. Run the tests (unittest is used). This can be done with a button click within VS Code, or with the following command where you need to be inside the root folder of the project:
```bash
python3 -m unittest discover -s ./tests -p '*.py'
```
6. Test your version thoroughly to catch as many bugs as possible (if any).

## Styling guide
The code of Kapowarr is written in such way that it follows the following rules. Your code should too.

1. Compatible with python 3.8 to 3.11 .
2. Tabs (4 space size) are used for indentation.
3. Use type hints as much as possible. If you encounter an import loop because something needs to be imported for type hinting, utilise [`typing.TYPE_CHECKING`](https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING).
4. Each function in the backend needs a doc string describing the function, what the inputs are, what errors could be raised from within the function and what the output is.
5. The imports need to be sorted (the extension `isort` is used in VS Code).
6. The code needs to be compatible with Linux, MacOS, Windows and the Docker container.
7. The code should, though not strictly enforced, reasonably comply with the rule of 80 characters per line.
