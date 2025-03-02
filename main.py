#!/bin/python
import argparse
from typing import Generator, Literal
from rich import print

# persistent python console
class PersistentPythonConsole:
    def __init__(self):
        self.locals = {}

    def execute(self, code: str):
        exec(code, self.locals)

def argparse_setup() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute python script printing also the multiline comments")
    parser.add_argument("filename", type=str, help="The python file to execute")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run the script in interactive mode")
    return parser.parse_args()

def split_code_every_multiline_comment(filename) -> Generator[tuple[str, Literal["code", "comment"]]]:
    # expecting a file content with code snippets intercalated with multiline comments, separate it and return
    # iterate over the lines
    with open(filename, "r") as f:
        line = f.readline()
        while line:
            if line.startswith('"""'):
                # multiline comment
                multiline_comment: str = line
                while True:
                    line = f.readline()
                    if not line or '"""' in line: break
                    else: multiline_comment += line
                # remove the two """ from the comment
                multiline_comment = multiline_comment[4:]
                yield (multiline_comment, "comment")
                line = f.readline()
            else:
                # code
                code = line
                while True:
                    line = f.readline()
                    if not line or '"""' in line: break
                    else: code += line
                yield (code, "code")

def python_w_multiline_comments(filename: str, interactive: bool = False):
    console = PersistentPythonConsole()
    for code_or_comment, type_ in split_code_every_multiline_comment(filename):
        if type_ == "comment": print(f"[bold white]{code_or_comment}[/bold white]", end="")
        elif type_ == "code":
            # execute the code and print the output
            try: console.execute(code_or_comment)
            except Exception as e: print(f"[bold dark_orange3]An error occurred:[/bold dark_orange3]\n[bold red]{e}[/bold red]")
        if interactive:
            in_val = input()
            if in_val == "q": break

if __name__ == "__main__":
    args = argparse_setup()
    python_w_multiline_comments(args.filename, interactive=args.interactive)
