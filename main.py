#!/bin/python
import argparse
from enum import Enum
from typing import Generator
from rich import print

# persistent python console
class PersistentPythonConsole:
    def __init__(self):
        self.locals = {}

    def execute(self, code: str):
        exec(code, self.locals)

class RequiresInteractive(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not namespace.interactive:
            parser.error(f"{option_string} requires the interactive mode")
        setattr(namespace, self.dest, values)

def parse_fast_forward(ff: str) -> str | int:
    try: return int(ff)
    except ValueError: return ff

def argparse_setup() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute python script printing also the multiline comments")
    parser.add_argument("filename", type=str, help="The python file to execute")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run the script in interactive mode")
    parser.add_argument("-ff", "--fast-forward", type=parse_fast_forward, action=RequiresInteractive,
                        help="Fast forward the execution to the Nth snippet or to the comment containing the specified string.\n"
                             "(only in interactive mode)")
    return parser.parse_args()

class SnippetType(Enum):
    code = "code"
    comment = "comment"

def split_code_every_multiline_comment(filename) -> Generator[tuple[str, SnippetType]]:
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
                yield (multiline_comment, SnippetType.comment)
                line = f.readline()
            else:
                # code
                code = line
                while True:
                    line = f.readline()
                    if not line or '"""' in line: break
                    else: code += line
                yield (code, SnippetType.code)

def is_code_to_execute(snippet: str) -> bool:
    # check if the snippet starts with a comment with `pwmc:disable` or not
    snippet = snippet.strip()
    return not (snippet.startswith("# pwmc:no_exec") or snippet.startswith("#pwmc:no_exec"))

def python_w_multiline_comments(filename: str, interactive: bool = False, fast_forward: str | int | None = None):
    console = PersistentPythonConsole()
    snippet_counter = 0
    snippet_to_fast_forward_passed = False
    for code_or_comment, type_ in split_code_every_multiline_comment(filename):
        if type_ == SnippetType.comment:
            print(f"[bold white]{code_or_comment}[/bold white]", end="")
            if interactive and fast_forward and type(fast_forward) is str and fast_forward in code_or_comment:
                snippet_to_fast_forward_passed = True
        elif type_ == SnippetType.code:
            # execute the code and print the output
            try:
                if not is_code_to_execute(code_or_comment): print(f"[green]Code not executed[/green]")
                else: console.execute(code_or_comment)
            except Exception as e: print(f"[bold dark_orange3]An error occurred:[/bold dark_orange3]\n[bold red]{e}[/bold red]")
        snippet_counter += 1
        if interactive:
            if fast_forward:
                if type(fast_forward) is int and snippet_counter <= fast_forward: continue
                if type(fast_forward) is str and not snippet_to_fast_forward_passed: continue
            in_val = input()
            if in_val == "q": break

if __name__ == "__main__":
    args = argparse_setup()
    python_w_multiline_comments(args.filename, interactive=args.interactive, fast_forward=args.fast_forward)
