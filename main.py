#!/bin/python
import argparse
from enum import Enum
from typing import Generator
from rich import print

# persistent python console
class PersistentPythonConsole:
    def __init__(self):
        self.locals = {}

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
            with self.NoPlotsContext():
                exec(code, self.locals)
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
        if type(self.fast_forward) is str and self.fast_forward in comment:
            self.snippet_to_fast_forward_passed = True
        return self.snippet_to_fast_forward_passed

    def is_fast_forwarding(self) -> bool:
        if type(self.fast_forward) is int and self.snippet_counter <= self.fast_forward: return True
        if type(self.fast_forward) is str and not self.snippet_to_fast_forward_passed: return True
        return False

    def check_fast_forward(self):
        if type(self.fast_forward) is int and self.snippet_counter <= self.fast_forward: return True
        if type(self.fast_forward) is str and not self.snippet_to_fast_forward_passed: return True
        return False

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
                if len(line) > 4 and line.endswith(END_COMMENT):
                    multiline_comment = line[3:-4] + "\n"
                else:
                    # if the comment starts in the next line than discard the first line with only `"""`
                    # otherwise remove the `"""` from the first line and add the rest of the line to the comment
                    if line != (START_COMMENT + '\n'):
                        multiline_comment = line[3:]
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
                    if not line or START_COMMENT in line: break
                    else: code += line
                yield (code, SnippetType.code)

def is_code_to_execute(snippet: str) -> bool:
    # check if the snippet starts with a comment with `pwmc:disable` or not
    snippet = snippet.strip()
    return not (snippet.startswith("# pwmc:no_exec") or snippet.startswith("#pwmc:no_exec"))

def python_w_multiline_comments(filename: str, interactive: bool = False, fast_forward: str | int | None = None):
    console = PersistentPythonConsole()
    fast_forward_handler = FastForwardHandler(fast_forward) if fast_forward else None
    for code_or_comment, type_ in split_code_every_multiline_comment(filename):
        if type_ == SnippetType.comment:
            print(f"[bold white]{code_or_comment}[/bold white]")
            if interactive and fast_forward_handler:
                fast_forward_handler.is_snippet_to_fast_forward_passed(code_or_comment)
        elif type_ == SnippetType.code:
            # execute the code and print the output
            try:
                if not is_code_to_execute(code_or_comment): print(f"[green]Code not executed[/green]")
                else: console.execute(code_or_comment, suppress_plots=fast_forward_handler.is_fast_forwarding() if fast_forward_handler else False)
                print()
            except Exception as e: print(f"[bold dark_orange3]An error occurred:[/bold dark_orange3]\n[bold red]{e}[/bold red]")
        if fast_forward_handler: fast_forward_handler.increment_snippet_counter()
        if interactive:
            if fast_forward_handler and fast_forward_handler.check_fast_forward(): continue
            in_val = input()
            if in_val == "q": break

if __name__ == "__main__":
    args = argparse_setup()
    python_w_multiline_comments(args.filename, interactive=args.interactive, fast_forward=args.fast_forward)
