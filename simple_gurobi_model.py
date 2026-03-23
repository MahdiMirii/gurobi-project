"""
Simple Gurobi optimization model in Python.

Model:
    Maximize:   3x + 2y
    Subject to: x + 2y <= 14
                3x - y <= 0
                x - y <= 2
                x, y >= 0
"""

import gurobipy as gp
from gurobipy import GRB


def main() -> None:
    # Create and name a new optimization model
    model = gp.Model("simple_lp")

    # Decision variables (continuous, non-negative)
    x = model.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="x")
    y = model.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="y")

    # Objective: maximize 3x + 2y
    model.setObjective(3 * x + 2 * y, GRB.MAXIMIZE)

    # Constraints
    model.addConstr(x + 2 * y <= 14, name="c1")
    model.addConstr(3 * x - y <= 0, name="c2")
    model.addConstr(x - y <= 2, name="c3")

    # Solve model
    model.optimize()

    # Print solution
    if model.status == GRB.OPTIMAL:
        print("\nOptimal solution found:")
        print(f"x = {x.X:.4f}")
        print(f"y = {y.X:.4f}")
        print(f"Objective value = {model.objVal:.4f}")
    else:
        print(f"No optimal solution found. Solver status: {model.status}")


if __name__ == "__main__":
    main()
