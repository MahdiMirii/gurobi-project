"""
Two-stage stochastic closed-loop supply chain model (Gurobi).

This script uses small dummy sets and placeholder parameters only.
Replace values in `build_dummy_data()` with your real data later.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import gurobipy as gp
from gurobipy import GRB


def build_dummy_data() -> Dict[str, Any]:
    """Create compact placeholder sets and parameters."""
    data: Dict[str, Any] = {}

    # Sets
    data["S"] = ["S1", "S2"]  # suppliers
    data["M"] = ["M1", "M2"]  # manufacturers
    data["O"] = ["O1"]  # OEM nodes
    data["U"] = ["U1", "U2"]  # end users
    data["C"] = ["C1"]  # collection centers
    data["R"] = ["R1"]  # recycling centers
    data["D"] = ["D1"]  # disposal centers
    data["G"] = ["Li", "Ni"]  # materials
    data["B"] = ["EV"]  # battery types
    data["T"] = [1, 2]  # time periods
    data["Omega"] = ["base", "stress"]  # scenarios

    S = data["S"]
    M = data["M"]
    O = data["O"]
    U = data["U"]
    C = data["C"]
    R = data["R"]
    D = data["D"]
    G = data["G"]
    B = data["B"]
    T = data["T"]
    Omega = data["Omega"]

    # Scenario adjustments (capacity/cost)
    data["cap_mult"] = {"base": 1.00, "stress": 0.85}
    data["cost_mult"] = {"base": 1.00, "stress": 1.25}

    # Reference cost per scenario for regret computation
    data["regret_reference"] = {"base": 1700.0, "stress": 2100.0}

    # First-stage fixed costs
    data["fix_supplier"] = {"S1": 120.0, "S2": 100.0}
    data["fix_manufacturer"] = {"M1": 260.0, "M2": 240.0}
    data["fix_collection"] = {"C1": 110.0}
    data["fix_recycling"] = {"R1": 180.0}

    # Capacities
    data["cap_supply"] = {
        (s, g, t): 120.0 if s == "S1" else 100.0
        for s in S
        for g in G
        for t in T
    }
    data["cap_manufacturer"] = {(m, t): 140.0 for m in M for t in T}
    data["cap_collection"] = {(c, t): 80.0 for c in C for t in T}
    data["cap_recycling"] = {(r, t): 70.0 for r in R for t in T}
    data["cap_disposal"] = {(d, t): 40.0 for d in D for t in T}

    # Demand and return parameters
    data["demand"] = {
        (u, b, t, w): 24.0 if w == "base" else 20.0
        for u in U
        for b in B
        for t in T
        for w in Omega
    }
    data["return_rate"] = {"EV": 0.45}

    # Flow split minimum shares for returned batteries
    data["min_recycle_share"] = 0.50
    data["min_reman_share"] = 0.20
    data["min_second_life_share"] = 0.10

    # Material conversion and process yields
    data["material_content"] = {("EV", "Li"): 1.2, ("EV", "Ni"): 1.0}
    data["material_req"] = {("EV", "Li"): 1.0, ("EV", "Ni"): 0.8}
    data["recovery_yield"] = {"Li": 0.75, "Ni": 0.70}

    # Variable costs (placeholders)
    data["c_x"] = {(s, m, g): 2.0 for s in S for m in M for g in G}
    data["c_q"] = {(m, o, b): 3.0 for m in M for o in O for b in B}
    data["c_v"] = {(o, u, b): 1.8 for o in O for u in U for b in B}
    data["c_r"] = {(u, c, b): 1.1 for u in U for c in C for b in B}
    data["c_k"] = {(c, r, b): 1.4 for c in C for r in R for b in B}
    data["c_l_rem"] = {(c, b): 0.9 for c in C for b in B}
    data["c_l_sl"] = {(c, b): 0.7 for c in C for b in B}
    data["c_h"] = {(r, m, g): 1.6 for r in R for m in M for g in G}
    data["c_delta"] = {(r, d, g): 2.3 for r in R for d in D for g in G}
    data["c_prod"] = {(m, b): 4.5 for m in M for b in B}

    # Big-M parameters for first-stage linking
    data["bigM_supplier"] = {s: 400.0 for s in S}

    return data


def build_model(data: Dict[str, Any]) -> Tuple[gp.Model, Dict[str, Any]]:
    """Build and return the Gurobi model and variable dictionary."""
    S = data["S"]
    M = data["M"]
    O = data["O"]
    U = data["U"]
    C = data["C"]
    R = data["R"]
    D = data["D"]
    G = data["G"]
    B = data["B"]
    T = data["T"]
    Omega = data["Omega"]

    model = gp.Model("two_stage_stochastic_supply_chain")

    # -------------------------
    # First-stage decision vars
    # -------------------------
    z_s = model.addVars(S, vtype=GRB.BINARY, name="z_s")
    y_m = model.addVars(M, vtype=GRB.BINARY, name="y_m")
    z_c = model.addVars(C, vtype=GRB.BINARY, name="z_c")
    w_r = model.addVars(R, vtype=GRB.BINARY, name="w_r")

    # --------------------------
    # Second-stage decision vars
    # --------------------------
    x = model.addVars(S, M, G, T, Omega, lb=0.0, name="x_smgtw")
    q = model.addVars(M, O, B, T, Omega, lb=0.0, name="q_mobtw")
    v = model.addVars(O, U, B, T, Omega, lb=0.0, name="v_oubtw")
    r = model.addVars(U, C, B, T, Omega, lb=0.0, name="r_ucbtw")
    k = model.addVars(C, R, B, T, Omega, lb=0.0, name="k_crbtw")
    l_rem = model.addVars(C, B, T, Omega, lb=0.0, name="l_rem")
    l_sl = model.addVars(C, B, T, Omega, lb=0.0, name="l_sl")
    h = model.addVars(R, M, G, T, Omega, lb=0.0, name="h_rmgtw")
    delta = model.addVars(R, D, G, T, Omega, lb=0.0, name="delta_rdgtw")
    P = model.addVars(M, B, T, Omega, lb=0.0, name="P_mbtw")
    Reg = model.addVars(Omega, lb=0.0, name="Reg")

    # Epigraph variable for min max_p sum_w p_w * Reg_w over simplex p:
    # worst-case expectation equals max scenario regret.
    worst_case_regret = model.addVar(lb=0.0, name="WorstCaseRegret")

    # ----------------
    # Core constraints
    # ----------------

    # Supplier capacity constraints
    model.addConstrs(
        (
            gp.quicksum(x[s, m, g, t, w] for m in M)
            <= data["cap_mult"][w] * data["cap_supply"][s, g, t]
            for s in S
            for g in G
            for t in T
            for w in Omega
        ),
        name="supplier_capacity",
    )

    # Supplier selection linking
    model.addConstrs(
        (
            gp.quicksum(x[s, m, g, t, w] for m in M for g in G for t in T)
            <= data["bigM_supplier"][s] * z_s[s]
            for s in S
            for w in Omega
        ),
        name="supplier_open_link",
    )

    # Manufacturer capacity
    model.addConstrs(
        (
            gp.quicksum(P[m, b, t, w] for b in B)
            <= data["cap_mult"][w] * data["cap_manufacturer"][m, t] * y_m[m]
            for m in M
            for t in T
            for w in Omega
        ),
        name="manufacturer_capacity",
    )

    # Material balance at manufacturers
    model.addConstrs(
        (
            gp.quicksum(x[s, m, g, t, w] for s in S)
            + gp.quicksum(h[r_, m, g, t, w] for r_ in R)
            >= gp.quicksum(data["material_req"][b, g] * P[m, b, t, w] for b in B)
            for m in M
            for g in G
            for t in T
            for w in Omega
        ),
        name="manufacturer_material_balance",
    )

    # Production flow from manufacturer to OEM
    model.addConstrs(
        (
            gp.quicksum(q[m, o, b, t, w] for o in O) <= P[m, b, t, w]
            for m in M
            for b in B
            for t in T
            for w in Omega
        ),
        name="production_to_oem",
    )

    # Flow balance at OEM nodes
    model.addConstrs(
        (
            gp.quicksum(q[m, o, b, t, w] for m in M)
            == gp.quicksum(v[o, u, b, t, w] for u in U)
            for o in O
            for b in B
            for t in T
            for w in Omega
        ),
        name="oem_flow_balance",
    )

    # Demand satisfaction
    model.addConstrs(
        (
            gp.quicksum(v[o, u, b, t, w] for o in O) >= data["demand"][u, b, t, w]
            for u in U
            for b in B
            for t in T
            for w in Omega
        ),
        name="demand_satisfaction",
    )

    # Return constraints
    model.addConstrs(
        (
            gp.quicksum(r[u, c, b, t, w] for c in C)
            <= data["return_rate"][b] * gp.quicksum(v[o, u, b, t, w] for o in O)
            for u in U
            for b in B
            for t in T
            for w in Omega
        ),
        name="returns_upper_bound",
    )

    # Collection capacity constraints
    model.addConstrs(
        (
            gp.quicksum(r[u, c, b, t, w] for u in U for b in B)
            <= data["cap_mult"][w] * data["cap_collection"][c, t] * z_c[c]
            for c in C
            for t in T
            for w in Omega
        ),
        name="collection_capacity",
    )

    # Flow split constraints at collection centers
    model.addConstrs(
        (
            gp.quicksum(r[u, c, b, t, w] for u in U)
            == gp.quicksum(k[c, r_, b, t, w] for r_ in R) + l_rem[c, b, t, w] + l_sl[c, b, t, w]
            for c in C
            for b in B
            for t in T
            for w in Omega
        ),
        name="collection_flow_split",
    )

    # Minimum split shares (recycling/reman/second-life)
    model.addConstrs(
        (
            gp.quicksum(k[c, r_, b, t, w] for r_ in R)
            >= data["min_recycle_share"] * gp.quicksum(r[u, c, b, t, w] for u in U)
            for c in C
            for b in B
            for t in T
            for w in Omega
        ),
        name="min_recycle_share",
    )
    model.addConstrs(
        (
            l_rem[c, b, t, w]
            >= data["min_reman_share"] * gp.quicksum(r[u, c, b, t, w] for u in U)
            for c in C
            for b in B
            for t in T
            for w in Omega
        ),
        name="min_reman_share",
    )
    model.addConstrs(
        (
            l_sl[c, b, t, w]
            >= data["min_second_life_share"] * gp.quicksum(r[u, c, b, t, w] for u in U)
            for c in C
            for b in B
            for t in T
            for w in Omega
        ),
        name="min_second_life_share",
    )

    # Recycling capacity constraints
    model.addConstrs(
        (
            gp.quicksum(k[c, r_, b, t, w] for c in C for b in B)
            <= data["cap_mult"][w] * data["cap_recycling"][r_, t] * w_r[r_]
            for r_ in R
            for t in T
            for w in Omega
        ),
        name="recycling_capacity",
    )

    # Material recovery balance
    model.addConstrs(
        (
            gp.quicksum(h[r_, m, g, t, w] for m in M)
            <= data["recovery_yield"][g]
            * gp.quicksum(
                data["material_content"][b, g] * k[c, r_, b, t, w] for c in C for b in B
            )
            for r_ in R
            for g in G
            for t in T
            for w in Omega
        ),
        name="material_recovery_balance",
    )

    # Disposal after recycling
    model.addConstrs(
        (
            gp.quicksum(delta[r_, d, g, t, w] for d in D)
            >= (1.0 - data["recovery_yield"][g])
            * gp.quicksum(
                data["material_content"][b, g] * k[c, r_, b, t, w] for c in C for b in B
            )
            for r_ in R
            for g in G
            for t in T
            for w in Omega
        ),
        name="disposal_after_recycling",
    )

    # Disposal center capacity
    model.addConstrs(
        (
            gp.quicksum(delta[r_, d, g, t, w] for r_ in R for g in G)
            <= data["cap_mult"][w] * data["cap_disposal"][d, t]
            for d in D
            for t in T
            for w in Omega
        ),
        name="disposal_capacity",
    )

    # ----------------------
    # Scenario cost and regret
    # ----------------------
    first_stage_cost = (
        gp.quicksum(data["fix_supplier"][s] * z_s[s] for s in S)
        + gp.quicksum(data["fix_manufacturer"][m] * y_m[m] for m in M)
        + gp.quicksum(data["fix_collection"][c] * z_c[c] for c in C)
        + gp.quicksum(data["fix_recycling"][r_] * w_r[r_] for r_ in R)
    )

    scenario_cost_expr: Dict[str, gp.LinExpr] = {}
    for w in Omega:
        variable_cost = (
            gp.quicksum(
                data["c_x"][s, m, g] * x[s, m, g, t, w]
                for s in S
                for m in M
                for g in G
                for t in T
            )
            + gp.quicksum(
                data["c_q"][m, o, b] * q[m, o, b, t, w]
                for m in M
                for o in O
                for b in B
                for t in T
            )
            + gp.quicksum(
                data["c_v"][o, u, b] * v[o, u, b, t, w]
                for o in O
                for u in U
                for b in B
                for t in T
            )
            + gp.quicksum(
                data["c_r"][u, c, b] * r[u, c, b, t, w]
                for u in U
                for c in C
                for b in B
                for t in T
            )
            + gp.quicksum(
                data["c_k"][c, r_, b] * k[c, r_, b, t, w]
                for c in C
                for r_ in R
                for b in B
                for t in T
            )
            + gp.quicksum(
                data["c_l_rem"][c, b] * l_rem[c, b, t, w] for c in C for b in B for t in T
            )
            + gp.quicksum(
                data["c_l_sl"][c, b] * l_sl[c, b, t, w] for c in C for b in B for t in T
            )
            + gp.quicksum(
                data["c_h"][r_, m, g] * h[r_, m, g, t, w]
                for r_ in R
                for m in M
                for g in G
                for t in T
            )
            + gp.quicksum(
                data["c_delta"][r_, d, g] * delta[r_, d, g, t, w]
                for r_ in R
                for d in D
                for g in G
                for t in T
            )
            + gp.quicksum(
                data["c_prod"][m, b] * P[m, b, t, w] for m in M for b in B for t in T
            )
        )
        scenario_cost_expr[w] = first_stage_cost + data["cost_mult"][w] * variable_cost

    model.addConstrs(
        (
            Reg[w] >= scenario_cost_expr[w] - data["regret_reference"][w]
            for w in Omega
        ),
        name="regret_definition",
    )
    model.addConstrs(
        (worst_case_regret >= Reg[w] for w in Omega),
        name="worst_case_regret_epigraph",
    )

    model.setObjective(worst_case_regret, GRB.MINIMIZE)

    vars_dict = {
        "z_s": z_s,
        "y_m": y_m,
        "z_c": z_c,
        "w_r": w_r,
        "x": x,
        "q": q,
        "v": v,
        "r": r,
        "k": k,
        "l_rem": l_rem,
        "l_sl": l_sl,
        "h": h,
        "delta": delta,
        "P": P,
        "Reg": Reg,
        "WorstCaseRegret": worst_case_regret,
    }
    return model, vars_dict


def solve_and_report(model: gp.Model, vars_dict: Dict[str, Any], data: Dict[str, Any]) -> None:
    """Solve and print a small summary."""
    model.optimize()

    if model.Status != GRB.OPTIMAL:
        print(f"Model status: {model.Status}")
        return

    print(f"\nOptimal worst-case regret: {vars_dict['WorstCaseRegret'].X:.4f}")

    print("\nSelected suppliers:")
    for s in data["S"]:
        if vars_dict["z_s"][s].X > 0.5:
            print(f"  {s}")

    print("\nOpen manufacturers:")
    for m in data["M"]:
        if vars_dict["y_m"][m].X > 0.5:
            print(f"  {m}")

    print("\nOpen collection centers:")
    for c in data["C"]:
        if vars_dict["z_c"][c].X > 0.5:
            print(f"  {c}")

    print("\nOpen recycling centers:")
    for r_ in data["R"]:
        if vars_dict["w_r"][r_].X > 0.5:
            print(f"  {r_}")

    print("\nScenario regrets:")
    for w in data["Omega"]:
        print(f"  {w}: {vars_dict['Reg'][w].X:.4f}")


def main() -> None:
    data = build_dummy_data()
    model, vars_dict = build_model(data)
    solve_and_report(model, vars_dict, data)


if __name__ == "__main__":
    main()
