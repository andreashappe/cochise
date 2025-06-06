#!/usr/bin/python3

import argparse

from analysis.index_duration import index_duration
from analysis.index_rounds_and_tokens import index_rounds_and_tokens
from analysis.index_rounds import index_rounds
from analysis.show_tokens import show_tokens
from rich.console import Console
from rich.table import Table

analysis_functions = {
        'index-duration': index_duration,
        'index-rounds': index_rounds,
        'index-rounds-and-tokens': index_rounds_and_tokens,
        'show-tokens': show_tokens,
}

def format_input(i):
    if '+/-' in i:
        return i.replace('+/-', '$\\pm$')
    return i

if __name__=='__main__':

    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('analysis', choices=analysis_functions.keys(), help='type of analysis to perform')
    parser.add_argument('input', type=argparse.FileType('r'), nargs='+', help='input file to analyze')
    parser.add_argument('--latex', action='store_true')
    parser.add_argument('--duration-min', default=600, type=int)
    parser.add_argument('--model-eq', default=None, type=str)
    parser.add_argument('--model-substr', default=None, type=str)
    args = parser.parse_args()

    def filter_result(result):
        if args.model_eq != None:
            if ','.join(sorted(result.models)) != args.model_eq:
                return False
        if args.model_substr != None:
            if args.model_substr not in (','.join(sorted(result.models))):
                return False
        return result.duration >= args.duration_min

    console = Console() 
    results = []

    if args.analysis in analysis_functions.keys():
        results = analysis_functions[args.analysis](console, args.input, filter_result)
    else:
        console.print(f"Unknown analysis type: {args.analysis}")
        exit(1)

    if args.latex == True:
        print("now doing latex output...")

        for table in results:
            print("\\begin{tabular}{c%s}" % ('r'*len(table.headers)))
            print("\\toprule")
            print(" & ".join(map(lambda i: "\\rot{\\textbf{%s}}" % (i), table.headers)), "\\\\")
            print("\\midrule")
            for r in table.rows:
                print( " & ".join(map(format_input, r)), "\\\\\\hdashline")
            print("\\midrule")
            print(" & ".join(map(lambda i: "\\textbf{%s}" % (i), map(format_input, table.footers))), "\\\\")
            print("\\bottomrule")
            print("\\end{tabular}")
    else:
        for table in results:
            t = Table(title=table.title, show_header=True, show_footer=len(table.footers) > 0)
            for i, h in enumerate(table.headers):
                if i < len(table.footers):
                    t.add_column(h, footer=table.footers[i])
                else:
                    t.add_column(h)
            for r in table.rows:
                t.add_row(*r)
            console.print(t)

