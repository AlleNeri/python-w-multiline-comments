#!/bin/python
import argparse
from enum import Enum
import os
import site
import sys
from typing import Generator, Literal

from rich import print
from rich.prompt import Confirm

# persistent python console
class PersistentPythonConsole:
    def __init__(self, module_path: list[str] | None = None, venv: Literal[True] | None = None):
        self.locals = {}
        self.python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        # detect an active venv
        venv_path = os.getenv("VIRTUAL_ENV")
        if venv_path and os.path.exists(venv_path) and venv_path not in sys.path:
            res = venv
            if venv is None: res = Confirm.ask("[green]Venv detected\nDo you want to active it?[/green]", case_sensitive=False, default=True)
            if res: self.activate_venv(venv_path)
            else: print("[red]Venv not activated[/red]")
        if module_path:
            # add the search path to the sys.path
            for path in module_path:
                if os.path.exists(path) and path not in sys.path: sys.path.append(path)
                else: print(f"[bold red]Path {path} is not a directory or already in sys.path[/bold red]")

    def activate_venv(self, venv_path: str):
        site_packages_path = os.path.join(venv_path, "lib", self.python_version, "site-packages")

        if site_packages_path not in sys.path:
            sys.path.insert(0, site_packages_path)
            site.addsitedir(site_packages_path)
        
        os.environ["VIRTUAL_ENV"] = venv_path
        os.environ["PYTHONNOUSERSITE"] = "1"

        print(f"[green]Activated venv site-packages from: {site_packages_path}[/green]")

    class NoPlotsContext:
        def __enter__(self):
            import matplotlib.pyplot as plt
            self.original_show = plt.show
            plt.show = lambda *_, **__: None

        def __exit__(self, _, __, ___):
            import matplotlib.pyplot as plt
            plt.show = self.original_show
            plt.close("all")

    def execute(self, code: str, suppress_plots: bool = False):
        if suppress_plots:
            with self.NoPlotsContext(): exec(code, self.locals)
        else: exec(code, self.locals)

class FastForwardHandler:
    def __init__(self, fast_forward: int | str):
        self.fast_forward = fast_forward
        self.snippet_counter = 0
        self.snippet_to_fast_forward_passed = False

    def increment_snippet_counter(self):
        self.snippet_counter += 1

    def is_snippet_to_fast_forward_passed(self, comment: str | None = None) -> bool:
        if not comment or self.snippet_to_fast_forward_passed: return self.snippet_to_fast_forward_passed
        if type(self.fast_forward) is str and self.fast_forward in comment.lower(): self.snippet_to_fast_forward_passed = True
        return self.snippet_to_fast_forward_passed

    def is_fast_forwarding(self) -> bool:
        if type(self.fast_forward) is int and self.snippet_counter <= self.fast_forward: return True
        if type(self.fast_forward) is str and not self.snippet_to_fast_forward_passed: return True
        return False

def parse_fast_forward(ff: str) -> str | int:
    try: return int(ff)
    except ValueError: return ff.lower()

def argparse_setup() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute python script printing also the multiline comments. All the code snippets starting with the single line comment `pwmc:no_exec` won't be executed.")
    parser.add_argument("filename", type=str, help="The python file to execute")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-a", "--all", action="store_true", help="Run all the script in non-interactive mode")
    group.add_argument("-ff", "--fast-forward", type=parse_fast_forward,
                        help="Fast forward the execution to the Nth snippet or to the comment containing the specified string.\n"
                             "(only in interactive mode)")
    parser.add_argument("-l", "--load-path", type=str, nargs="+", default=None,
                        help="Additional paths to load modules from. If not specified, the current directory is used.")
    parser.add_argument("--venv", action="store_true", default=None,
                        help="Activate the virtual environment if detected. If not specified, the user will be prompted to activate it.")
    return parser.parse_args()

class SnippetType(Enum):
    code = "code"
    comment = "comment"

START_COMMENT = '"""'
END_COMMENT = START_COMMENT + "\n"

def split_code_every_multiline_comment(filename) -> Generator[tuple[str, SnippetType]]:
    # expecting a file content with code snippets intercalated with multiline comments, separate it and return
    # iterate over the lines
    with open(filename, "r") as f:
        line = f.readline()
        while line:
            if line.startswith(START_COMMENT):
                # multiline comment
                multiline_comment: str = ""
                # single line multiline comment :(
                if len(line) > 4 and line.endswith(END_COMMENT): multiline_comment = line[3:-4] + "\n"
                else:
                    # if the comment starts in the next line than discard the first line with only `"""`
                    # otherwise remove the `"""` from the first line and add the rest of the line to the comment
                    if line != (START_COMMENT + '\n'): multiline_comment = line[3:]
                    # iterate over the lines until the end of the comment
                    while True:
                        line = f.readline()
                        # if the comment ends break the loop otherwise add the line to the comment
                        if not line or line.endswith(END_COMMENT):
                            # if there are some contents in the line add them to the comment
                            if line and line != END_COMMENT: multiline_comment += line[:-4] + "\n"
                            break
                        else: multiline_comment += line
                yield (multiline_comment, SnippetType.comment)
                line = f.readline()
            else:
                # code
                code = line
                while True:
                    line = f.readline()
                    # EOF reached
                    if not line: break
                    # line is a multiline comment
                    elif line.startswith(START_COMMENT):
                        # if it's a docstring, ignore it; otherwise break the loop
                        prev_line = code.split("\n")[-2].strip()
                        if prev_line.endswith(":") and (prev_line.startswith("def ") or prev_line.startswith("class ")):
                            # consume all the lines until the end of the docstring
                            while True:
                                if line.endswith(END_COMMENT):
                                    break
                                line = f.readline()
                        else: break
                    else: code += line
                yield (code, SnippetType.code)

def is_code_to_execute(snippet: str) -> bool:
    # check if the snippet starts with the comment `pwmc:no_exec` or not
    snippet = snippet.strip()
    return not (snippet.startswith("# pwmc:no_exec") or snippet.startswith("#pwmc:no_exec"))

def python_w_multiline_comments(filename: str, interactive: bool = True, fast_forward: str | int | None = None,
                                module_path: list[str] | None = None, venv: Literal[True] | None = None):
    if module_path is None: module_path = ["."]  # default to current directory
    console = PersistentPythonConsole(module_path, venv=venv)
    fast_forward_handler = FastForwardHandler(fast_forward) if fast_forward else None
    for code_or_comment, type_ in split_code_every_multiline_comment(filename):
        if type_ == SnippetType.comment:
            print(f"[bold white]{code_or_comment}[/bold white]", end="")
            if interactive and fast_forward_handler: fast_forward_handler.is_snippet_to_fast_forward_passed(code_or_comment)
        elif type_ == SnippetType.code:
            # execute the code and print the output
            try:
                if not is_code_to_execute(code_or_comment): print(f"[green]Code not executed[/green]")
                elif fast_forward_handler: console.execute(code_or_comment, suppress_plots=fast_forward_handler.is_fast_forwarding())
                else: console.execute(code_or_comment, suppress_plots=not interactive)
            except Exception as e: print(f"[bold dark_orange3]An error occurred:[/bold dark_orange3]\n[bold red]{e}[/bold red]")
        if fast_forward_handler and fast_forward_handler.is_fast_forwarding(): fast_forward_handler.increment_snippet_counter()
        if interactive:
            if fast_forward_handler and fast_forward_handler.is_fast_forwarding():
                print() # separate the snippets
                continue
            in_val = input()
            if in_val == "q": break
        else: print()

if __name__ == "__main__":
    args = argparse_setup()
    python_w_multiline_comments(args.filename, interactive=not args.all, fast_forward=args.fast_forward, module_path=args.load_path, venv=args.venv)
