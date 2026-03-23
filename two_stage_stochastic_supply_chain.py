"""
Two-stage stochastic closed-loop supply chain model (Gurobi).

This version is a regret-based base model (no DRO dual reformulation yet).
All data are placeholders on small dummy sets so you can replace them easily.
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
    data["T"] = [1, 2]  # periods
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

    # Regret reference cost per scenario (placeholder)
    data["regret_reference"] = {"base": 1700.0, "stress": 2100.0}

    # First-stage fixed costs
    data["fix_supplier"] = {"S1": 120.0, "S2": 100.0}
    data["fix_manufacturer"] = {"M1": 260.0, "M2": 240.0}
    data["fix_collection"] = {"C1": 110.0}
    data["fix_recycling"] = {"R1": 180.0}

    # Base supplier capacity and scenario-effective supplier capacity:
    # cap_eff[s,g,t,w] = cap_supply_base[s,g,t] * (1 - disruption_rate[s,w])
    data["cap_supply_base"] = {
        (s, g, t): 120.0 if s == "S1" else 100.0
        for s in S
        for g in G
        for t in T
    }
    data["disruption_rate"] = {
        ("S1", "base"): 0.00,
        ("S1", "stress"): 0.15,
        ("S2", "base"): 0.00,
        ("S2", "stress"): 0.20,
    }
    data["cap_supply_eff"] = {
        (s, g, t, w): data["cap_supply_base"][s, g, t] * (1.0 - data["disruption_rate"][s, w])
        for s in S
        for g in G
        for t in T
        for w in Omega
    }

    # Battery-type dependent capacities
    data["cap_manufacturer"] = {(m, b, t): 80.0 for m in M for b in B for t in T}
    data["cap_collection"] = {(c, b, t): 55.0 for c in C for b in B for t in T}
    data["cap_recycling"] = {(r, b, t): 45.0 for r in R for b in B for t in T}
    data["cap_disposal"] = {(d, t): 45.0 for d in D for t in T}

    # Demand and returns
    data["demand"] = {
        (u, b, t, w): 24.0 if w == "base" else 20.0
        for u in U
        for b in B
        for t in T
        for w in Omega
    }
    data["return_rate"] = {"EV": 0.45}

    # Exact split coefficients at collection
    data["phi"] = {"EV": 0.60}  # recycling share
    data["psi"] = {"EV": 0.25}  # remanufacturing share
    data["chi"] = {"EV": 0.15}  # second-life share

    # Material conversion and yields
    data["material_content"] = {("EV", "Li"): 1.2, ("EV", "Ni"): 1.0}
    data["material_req"] = {("EV", "Li"): 1.0, ("EV", "Ni"): 0.8}
    data["recovery_yield"] = {"Li": 0.75, "Ni": 0.70}

    # Scenario-dependent procurement cost:
    # c_x[s,m,g,w] = c_x_base[s,m,g] * (1 + procurement_markup[s,w])
    data["c_x_base"] = {(s, m, g): 2.0 for s in S for m in M for g in G}
    data["procurement_markup"] = {
        ("S1", "base"): 0.00,
        ("S1", "stress"): 0.20,
        ("S2", "base"): 0.00,
        ("S2", "stress"): 0.30,
    }
    data["c_x"] = {
        (s, m, g, w): data["c_x_base"][s, m, g] * (1.0 + data["procurement_markup"][s, w])
        for s in S
        for m in M
        for g in G
        for w in Omega
    }

    # Other variable costs (placeholders)
    data["c_q"] = {(m, o, b): 3.0 for m in M for o in O for b in B}
    data["c_v"] = {(o, u, b): 1.8 for o in O for u in U for b in B}
    data["c_r"] = {(u, c, b): 1.1 for u in U for c in C for b in B}
    data["c_k"] = {(c, r, b): 1.4 for c in C for r in R for b in B}
    data["c_l_rem"] = {(c, b): 0.9 for c in C for b in B}
    data["c_l_sl"] = {(c, b): 0.7 for c in C for b in B}
    data["c_h"] = {(r, m, g): 1.6 for r in R for m in M for g in G}
    data["c_delta"] = {(r, d, g): 2.3 for r in R for d in D for g in G}
    data["c_prod"] = {(m, b): 4.5 for m in M for b in B}

    # Big-M for supplier linking
    data["bigM_supplier"] = {s: 400.0 for s in S}

    validate_dummy_data(data)
    return data


def validate_dummy_data(data: Dict[str, Any]) -> None:
    """Sanity checks on split parameters and capacities."""
    for b in data["B"]:
        total_share = data["phi"][b] + data["psi"][b] + data["chi"][b]
        if abs(total_share - 1.0) > 1e-9:
            raise ValueError(f"Split coefficients for battery {b} must sum to 1.0.")


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
    # worst-case expectation is max_w Reg[w] in this base regret model.
    worst_case_regret = model.addVar(lb=0.0, name="WorstCaseRegret")

    # ----------------
    # Core constraints
    # ----------------

    # Supplier capacity constraints (scenario-effective capacity)
    model.addConstrs(
        (
            gp.quicksum(x[s, m, g, t, w] for m in M)
            <= data["cap_supply_eff"][s, g, t, w]
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

    # Manufacturer capacity (battery-type dependent)
    model.addConstrs(
        (
            P[m, b, t, w] <= data["cap_manufacturer"][m, b, t] * y_m[m]
            for m in M
            for b in B
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

    # Return constraints (exact equality)
    model.addConstrs(
        (
            gp.quicksum(r[u, c, b, t, w] for c in C)
            == data["return_rate"][b] * gp.quicksum(v[o, u, b, t, w] for o in O)
            for u in U
            for b in B
            for t in T
            for w in Omega
        ),
        name="returns_exact",
    )

    # Collection capacity constraints (battery-type dependent)
    model.addConstrs(
        (
            gp.quicksum(r[u, c, b, t, w] for u in U)
            <= data["cap_collection"][c, b, t] * z_c[c]
            for c in C
            for b in B
            for t in T
            for w in Omega
        ),
        name="collection_capacity",
    )

    # Exact split constraints with phi_b, psi_b, chi_b
    model.addConstrs(
        (
            gp.quicksum(k[c, r_, b, t, w] for r_ in R)
            == data["phi"][b] * gp.quicksum(r[u, c, b, t, w] for u in U)
            for c in C
            for b in B
            for t in T
            for w in Omega
        ),
        name="split_recycling_exact",
    )
    model.addConstrs(
        (
            l_rem[c, b, t, w]
            == data["psi"][b] * gp.quicksum(r[u, c, b, t, w] for u in U)
            for c in C
            for b in B
            for t in T
            for w in Omega
        ),
        name="split_reman_exact",
    )
    model.addConstrs(
        (
            l_sl[c, b, t, w]
            == data["chi"][b] * gp.quicksum(r[u, c, b, t, w] for u in U)
            for c in C
            for b in B
            for t in T
            for w in Omega
        ),
        name="split_second_life_exact",
    )

    # Recycling capacity constraints (battery-type dependent)
    model.addConstrs(
        (
            gp.quicksum(k[c, r_, b, t, w] for c in C)
            <= data["cap_recycling"][r_, b, t] * w_r[r_]
            for r_ in R
            for b in B
            for t in T
            for w in Omega
        ),
        name="recycling_capacity",
    )

    # Recycling recovery/disposal constraints (exact equalities)
    model.addConstrs(
        (
            gp.quicksum(h[r_, m, g, t, w] for m in M)
            == data["recovery_yield"][g]
            * gp.quicksum(
                data["material_content"][b, g] * k[c, r_, b, t, w] for c in C for b in B
            )
            for r_ in R
            for g in G
            for t in T
            for w in Omega
        ),
        name="material_recovery_exact",
    )
    model.addConstrs(
        (
            gp.quicksum(delta[r_, d, g, t, w] for d in D)
            == (1.0 - data["recovery_yield"][g])
            * gp.quicksum(
                data["material_content"][b, g] * k[c, r_, b, t, w] for c in C for b in B
            )
            for r_ in R
            for g in G
            for t in T
            for w in Omega
        ),
        name="disposal_after_recycling_exact",
    )

    # Disposal center capacity
    model.addConstrs(
        (
            gp.quicksum(delta[r_, d, g, t, w] for r_ in R for g in G)
            <= data["cap_disposal"][d, t]
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
                data["c_x"][s, m, g, w] * x[s, m, g, t, w]
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
        scenario_cost_expr[w] = first_stage_cost + variable_cost

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
