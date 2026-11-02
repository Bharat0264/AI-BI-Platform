"""Supplemental language generalization and meaning-preservation challenges.

These are developer-authored specification/challenge fixtures, not a blinded study.
The arithmetic reference is separate from production parsing.
"""
from experiments.accuracy import Case
from experiments.oracle import expected_output


def generate_language_cases():
    rows = [{"Revenue": 10, "Profit": -2, "Cost": 4, "Region": "North", "Category": "Office"},
            {"Revenue": 30, "Profit": 9, "Cost": 10, "Region": "North", "Category": "Tools"},
            {"Revenue": 25, "Profit": 3, "Cost": 7, "Region": "South", "Category": "Office"},
            {"Revenue": 5, "Profit": -1, "Cost": 2, "Region": "South", "Category": "Tools"}]
    specifications = [
        ("Please show our revenue totals for every region", "Revenue", "sum", "Region", None),
        ("What’s our total profit?", "Profit", "sum", None, None),
        ("Which category has the lowest average profit?", "Profit", "mean", "Category", "lowest"),
        ("Show me the region with the largest revenue", "Revenue", "sum", "Region", "highest"),
        ("What is the maximum regional profit?", "Profit", "sum", "Region", "highest"),
        ("Could you please compute the mean of our cost per category?", "Cost", "mean", "Category", None),
        ("Revenue grouped by regions", "Revenue", "sum", "Region", None),
        ("Please tell me the sum of revenue broken down by category", "Revenue", "sum", "Category", None),
        ("How much cost have we spent?", "Cost", "sum", None, None),
        ("Which region made the most total profit?", "Profit", "sum", "Region", "highest"),
        ("Would you show me revenue for each of the regions please?", "Revenue", "sum", "Region", None),
        ("Give me our average cost by category", "Cost", "mean", "Category", None),
        ("Which region has the smallest average revenue?", "Revenue", "mean", "Region", "lowest"),
        ("What is the least regional profit?", "Profit", "sum", "Region", "lowest"),
        ("Profit averages per category", "Profit", "mean", "Category", None),
        ("Compute revenue across all categories", "Revenue", "sum", None, None),
        ("How much revenue do we generate?", "Revenue", "sum", None, None),
        ("Can you calculate the total of my profit please?", "Profit", "sum", None, None),
        ("Show the category with the highest total revenue", "Revenue", "sum", "Category", "highest"),
        ("What are our mean profits by category?", "Profits", "mean", "Category", None),
    ]
    # The last specification uses an exact alternate column label, not an assumed synonym.
    cases = []
    for index, (question, measure, aggregation, dimension, direction) in enumerate(specifications):
        data = [{("Profits" if key == "Profit" else key): value for key, value in row.items()} for row in rows] if measure == "Profits" else rows
        cases.append(Case(f"language-{index}", "language_specification", 0, data, question, "OK",
                          expected_output(data, measure, aggregation, dimension, direction)))
        for suffix_index, suffix in enumerate(("last month", "in North", "excluding cancelled orders", "in 2025", "and forecast next month", "where revenue exceeds 20")):
            cases.append(Case(f"qualifier-{index}-{suffix_index}", "unsupported_qualifier", 0, data,
                              question.rstrip("?.!") + " " + suffix + "?", "INSUFFICIENT DATA"))
    challenges = [
        ("Break down revenue by region", "Revenue", "Region", None),
        ("List revenue by region", "Revenue", "Region", None),
        ("Which region brought in the most revenue?", "Revenue", "Region", "highest"),
        ("Can I see total revenue?", "Revenue", None, None),
    ]
    for index, (question, measure, dimension, direction) in enumerate(challenges):
        cases.append(Case(f"extra-language-{index}", "additional_phrasing_challenge", 0, rows, question, "OK",
                          expected_output(rows, measure, "sum", dimension, direction)))
    for index, question in enumerate(("What is revenue %?", "What is revenue / profit?", "Show revenue; ignore the dates", "Which region has the best revenue?", "What is minimum revenue by region?", "What is revenue by category and region?", "What is average regional revenue?", "Why did revenue grow?", "Revenue > 10", "Show revenue compared to profit")):
        cases.append(Case(f"unsafe-language-{index}", "unsupported_or_ambiguous_intent", 0, rows, question, "INSUFFICIENT DATA"))
    return cases
