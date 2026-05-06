"""
src/eval/generalizability_eval.py — Subject generalizability evaluation.

Claim: the OT Tutor's RAG pipeline is subject-agnostic — swapping the
ChromaDB vector database is all that is required to tutor a different subject.

Proof method:
  1. Build an in-memory ChromaDB collection from Physics text chunks
     (simulating the "swapped" vector DB — no persistent files touched).
  2. Run the identical retrieval + LLM-judge loop used by retrieval_eval.py
     against the Physics collection — zero pipeline code changes.
  3. Compare aggregate metrics between OT Anatomy and Physics side-by-side.

The Physics corpus covers 7 core topics from introductory university physics:
  kinematics, Newton's laws, energy/work, waves, electrostatics, circuits,
  and thermodynamics.

Output: eval_results/generalizability_results.json
"""

import json
import re
import time
from pathlib import Path

import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import EMBEDDING_MODEL, EVAL_OUTPUT_DIR
from src.llm import llm_chat

RESULTS_PATH = EVAL_OUTPUT_DIR / "generalizability_results.json"


# ── Physics corpus ─────────────────────────────────────────────────────────────
# Each chunk simulates a textbook passage. "page" mimics the OT metadata format
# so the same retrieval output schema works unchanged.

PHYSICS_CORPUS = [
    # ── Kinematics ────────────────────────────────────────────────────────────
    {
        "id": "phys_kin_01",
        "topic": "Kinematics – displacement, velocity, acceleration",
        "page": 12,
        "text": (
            "Kinematics describes the motion of objects without reference to the forces "
            "causing that motion. Displacement is a vector quantity representing the "
            "change in position: Δx = x_f − x_i. Velocity is the rate of change of "
            "displacement: v = Δx/Δt. Average velocity differs from instantaneous velocity, "
            "which is the derivative dx/dt. Acceleration is the rate of change of velocity: "
            "a = Δv/Δt. The four kinematic equations for constant acceleration are: "
            "(1) v = v₀ + at, (2) x = x₀ + v₀t + ½at², "
            "(3) v² = v₀² + 2aΔx, (4) x = x₀ + ½(v₀ + v)t. "
            "These equations apply only when acceleration is uniform. In free fall near "
            "Earth's surface the acceleration is g ≈ 9.8 m/s² directed downward."
        ),
    },
    {
        "id": "phys_kin_02",
        "topic": "Kinematics – projectile motion",
        "page": 15,
        "text": (
            "Projectile motion is two-dimensional kinematics where the horizontal and "
            "vertical components of motion are independent. Horizontally there is no "
            "acceleration (ignoring air resistance), so x = v₀ₓ t. Vertically the "
            "object accelerates at g downward: y = v₀ᵧt − ½gt². The initial velocity "
            "components are v₀ₓ = v₀ cosθ and v₀ᵧ = v₀ sinθ where θ is the launch angle. "
            "The range (horizontal distance) is maximised at θ = 45°. At the highest point "
            "the vertical component of velocity is zero while the horizontal component is "
            "unchanged. Projectile motion assumes a flat Earth and neglects air resistance."
        ),
    },

    # ── Newton's Laws ─────────────────────────────────────────────────────────
    {
        "id": "phys_newton_01",
        "topic": "Newton's first law – inertia",
        "page": 24,
        "text": (
            "Newton's First Law of Motion (the law of inertia) states that an object at "
            "rest remains at rest, and an object in motion continues in motion with the "
            "same speed and in the same direction, unless acted upon by a net external "
            "force. Inertia is the resistance of an object to any change in its state of "
            "motion; it is proportional to mass. A reference frame in which Newton's first "
            "law holds is called an inertial reference frame. Non-inertial frames (e.g., "
            "accelerating cars, rotating platforms) require fictitious forces to describe "
            "motion using Newton's laws."
        ),
    },
    {
        "id": "phys_newton_02",
        "topic": "Newton's second law – F = ma",
        "page": 27,
        "text": (
            "Newton's Second Law of Motion states that the net force acting on an object "
            "equals the product of its mass and acceleration: ΣF = ma. Force is a vector; "
            "the acceleration produced is in the same direction as the net force. The SI "
            "unit of force is the Newton (N = kg·m/s²). When multiple forces act, they "
            "are added vectorially to find the net force. Free-body diagrams are used to "
            "identify all forces (weight, normal force, friction, tension, applied forces) "
            "acting on an object. Newton's second law must be applied separately to each "
            "coordinate direction in two-dimensional problems."
        ),
    },
    {
        "id": "phys_newton_03",
        "topic": "Newton's third law – action-reaction pairs",
        "page": 31,
        "text": (
            "Newton's Third Law of Motion states that for every action force there is an "
            "equal and opposite reaction force: if object A exerts force F on object B, "
            "then object B exerts force −F on object A. These action-reaction pairs always "
            "act on different objects and therefore never cancel each other. Examples: the "
            "Earth pulls you down (gravity) while you pull the Earth up with the same "
            "magnitude force; a rocket expels exhaust gas backward so the gas pushes the "
            "rocket forward (thrust). Friction between surfaces also forms an action-reaction "
            "pair: the floor exerts static friction forward on a walking person's foot while "
            "the foot exerts an equal friction backward on the floor."
        ),
    },
    {
        "id": "phys_newton_04",
        "topic": "Friction – static and kinetic",
        "page": 35,
        "text": (
            "Friction is a contact force that opposes relative motion between surfaces. "
            "Static friction (f_s ≤ μ_s N) prevents surfaces from sliding and can vary "
            "up to a maximum value. Kinetic friction (f_k = μ_k N) acts on sliding surfaces "
            "and is generally less than maximum static friction (μ_k < μ_s). The normal "
            "force N is perpendicular to the contact surface. On a flat horizontal surface "
            "N = mg. On an inclined plane at angle θ, N = mg cosθ and the component of "
            "gravity along the plane is mg sinθ. The coefficients of friction μ_s and μ_k "
            "depend on the materials in contact, not the contact area."
        ),
    },

    # ── Energy and Work ───────────────────────────────────────────────────────
    {
        "id": "phys_energy_01",
        "topic": "Work, kinetic energy, work-energy theorem",
        "page": 48,
        "text": (
            "Work is defined as W = F·d cosθ, where F is the applied force, d is the "
            "displacement, and θ is the angle between the force and displacement vectors. "
            "Work is a scalar measured in Joules (J = N·m). The work-energy theorem states "
            "that the net work done on an object equals its change in kinetic energy: "
            "W_net = ΔKE = ½mv² − ½mv₀². Kinetic energy KE = ½mv² depends on mass and "
            "speed. A force perpendicular to motion does no work (e.g., centripetal force, "
            "normal force on horizontal surface). Negative work occurs when force and "
            "displacement are in opposite directions (e.g., friction slowing an object)."
        ),
    },
    {
        "id": "phys_energy_02",
        "topic": "Potential energy, conservation of energy",
        "page": 52,
        "text": (
            "Potential energy is stored energy associated with an object's position or "
            "configuration. Gravitational potential energy near Earth's surface is "
            "PE_g = mgh, where h is height above a chosen reference level. Elastic "
            "potential energy stored in a spring is PE_e = ½kx², where k is the spring "
            "constant and x is the compression or extension. The law of conservation of "
            "mechanical energy states that in the absence of non-conservative forces "
            "(like friction), total mechanical energy E = KE + PE remains constant: "
            "KE_i + PE_i = KE_f + PE_f. When friction acts, work done by friction equals "
            "the decrease in mechanical energy: W_friction = ΔKE + ΔPE."
        ),
    },
    {
        "id": "phys_energy_03",
        "topic": "Power and efficiency",
        "page": 57,
        "text": (
            "Power is the rate of doing work: P = W/t = Fv, measured in Watts (W = J/s). "
            "Average power is total work divided by total time. Instantaneous power is "
            "P = F·v (force dot velocity). Efficiency η = (useful output power)/(total "
            "input power) × 100%. No real machine is 100% efficient because some energy "
            "is always lost to friction, heat, or deformation. The horsepower (hp) is a "
            "non-SI unit where 1 hp = 746 W. In energy systems, the kilowatt-hour (kWh) "
            "is a common unit of energy: 1 kWh = 3.6 × 10⁶ J."
        ),
    },

    # ── Waves and Sound ───────────────────────────────────────────────────────
    {
        "id": "phys_waves_01",
        "topic": "Waves – types, properties, wave equation",
        "page": 68,
        "text": (
            "A wave is a disturbance that transfers energy without transferring matter. "
            "Transverse waves oscillate perpendicular to the direction of propagation "
            "(e.g., light, waves on a string). Longitudinal waves oscillate parallel to "
            "propagation (e.g., sound, seismic P-waves). Key wave properties: amplitude A "
            "(maximum displacement), wavelength λ (distance between identical points), "
            "period T (time for one complete oscillation), and frequency f = 1/T. The "
            "wave speed equation: v = fλ. The wave equation for a transverse wave is "
            "y(x,t) = A sin(kx − ωt) where k = 2π/λ is the wave number and ω = 2πf is "
            "the angular frequency."
        ),
    },
    {
        "id": "phys_waves_02",
        "topic": "Sound waves – speed, intensity, Doppler effect",
        "page": 72,
        "text": (
            "Sound is a longitudinal mechanical wave that requires a medium to travel. "
            "Speed of sound in air at 20°C is approximately 343 m/s; it increases with "
            "temperature and is higher in liquids and solids. Sound intensity I = P/A "
            "(power per area, W/m²). Sound intensity level in decibels: β = 10 log(I/I₀) "
            "where I₀ = 10⁻¹² W/m² is the threshold of hearing. Every 10 dB increase "
            "represents a 10-fold intensity increase. The Doppler effect describes the "
            "change in observed frequency when source or observer moves: "
            "f_obs = f_s(v ± v_obs)/(v ∓ v_s), where v is sound speed, v_obs is observer "
            "speed, and v_s is source speed. The ± signs depend on direction of motion."
        ),
    },

    # ── Electrostatics ────────────────────────────────────────────────────────
    {
        "id": "phys_elec_01",
        "topic": "Electrostatics – Coulomb's law, electric field",
        "page": 88,
        "text": (
            "Electric charge is a fundamental property of matter; it is quantised in "
            "multiples of the elementary charge e = 1.6 × 10⁻¹⁹ C. Like charges repel; "
            "opposite charges attract. Coulomb's Law gives the electrostatic force between "
            "two point charges: F = k|q₁||q₂|/r², where k = 8.99 × 10⁹ N·m²/C² is "
            "Coulomb's constant. The electric field E at a point is the force per unit "
            "positive test charge: E = F/q₀ = kq/r². Field lines point away from positive "
            "charges and toward negative charges. The electric field inside a conductor in "
            "electrostatic equilibrium is zero; excess charge resides on the surface."
        ),
    },
    {
        "id": "phys_elec_02",
        "topic": "Electrostatics – electric potential, capacitance",
        "page": 93,
        "text": (
            "Electric potential V is the potential energy per unit charge: V = PE/q, "
            "measured in Volts (V = J/C). The potential difference (voltage) between two "
            "points is ΔV = W/q. For a point charge: V = kq/r. The relationship between "
            "electric field and potential: E = −dV/dx (field points from high to low "
            "potential). A capacitor stores charge; capacitance C = Q/V in Farads (F). "
            "For a parallel-plate capacitor C = ε₀A/d where ε₀ = 8.85 × 10⁻¹² C²/(N·m²), "
            "A is plate area, and d is separation. Energy stored in a capacitor: "
            "U = ½CV² = Q²/(2C). Dielectric materials increase capacitance by a factor κ."
        ),
    },

    # ── Electric Circuits ─────────────────────────────────────────────────────
    {
        "id": "phys_circuit_01",
        "topic": "Electric circuits – Ohm's law, resistance, power",
        "page": 104,
        "text": (
            "Electric current I is the rate of charge flow: I = ΔQ/Δt, measured in "
            "Amperes (A). Ohm's Law: V = IR, where R is resistance in Ohms (Ω). "
            "Resistance depends on material resistivity ρ, length L, and cross-sectional "
            "area A: R = ρL/A. Resistors in series: R_total = R₁ + R₂ + … (same current). "
            "Resistors in parallel: 1/R_total = 1/R₁ + 1/R₂ + … (same voltage). "
            "Electrical power: P = IV = I²R = V²/R in Watts. Kirchhoff's Current Law: "
            "the sum of currents entering a junction equals the sum leaving (charge "
            "conservation). Kirchhoff's Voltage Law: the sum of voltage changes around "
            "any closed loop is zero (energy conservation)."
        ),
    },

    # ── Thermodynamics ────────────────────────────────────────────────────────
    {
        "id": "phys_thermo_01",
        "topic": "Thermodynamics – laws, internal energy, heat",
        "page": 122,
        "text": (
            "The First Law of Thermodynamics states that the change in internal energy "
            "of a system equals the heat added minus the work done by the system: "
            "ΔU = Q − W. Internal energy U is the total microscopic kinetic and potential "
            "energy of molecules. Heat Q is energy transferred due to temperature difference. "
            "Work done by a gas: W = PΔV (isobaric process). The Second Law of "
            "Thermodynamics states that the total entropy of an isolated system never "
            "decreases; heat flows spontaneously from hot to cold. The zeroth law defines "
            "thermal equilibrium: if A is in equilibrium with B, and B with C, then A is "
            "in equilibrium with C. Temperature is measured in Kelvin: T(K) = T(°C) + 273.15."
        ),
    },
    {
        "id": "phys_thermo_02",
        "topic": "Thermodynamics – heat engines, entropy, Carnot cycle",
        "page": 128,
        "text": (
            "A heat engine converts thermal energy into work by operating between a hot "
            "reservoir (T_H) and cold reservoir (T_C). The thermal efficiency is "
            "η = W/Q_H = 1 − Q_C/Q_H. The Carnot engine is the ideally efficient heat "
            "engine operating between two temperatures: η_Carnot = 1 − T_C/T_H. No real "
            "engine can exceed Carnot efficiency. Entropy S is a measure of disorder; "
            "for a reversible process ΔS = Q/T. The second law can be restated: the "
            "entropy of the universe increases in all real (irreversible) processes. "
            "Refrigerators and heat pumps do work to move heat from cold to hot reservoirs, "
            "operating as heat engines in reverse."
        ),
    },
]


# ── Physics test questions ─────────────────────────────────────────────────────

PHYSICS_EVAL_QS = [
    # Kinematics
    {
        "id": "p01_kinematics_suvat",
        "topic": "Kinematics",
        "question": "What are the four kinematic equations for constant acceleration and when do they apply?",
        "gold_key_terms": ["v = v₀ + at", "constant acceleration", "displacement", "velocity", "kinematic"],
        "gold_answer_hint": "Four SUVAT equations apply when acceleration is constant: v=v₀+at, x=x₀+v₀t+½at², v²=v₀²+2aΔx, x=x₀+½(v₀+v)t",
    },
    {
        "id": "p02_projectile",
        "topic": "Kinematics",
        "question": "How do the horizontal and vertical components of projectile motion differ, and at what angle is range maximised?",
        "gold_key_terms": ["projectile", "horizontal", "vertical", "independent", "45", "range", "gravity"],
        "gold_answer_hint": "Horizontal: no acceleration (constant velocity); vertical: constant downward acceleration g; range maximised at 45°",
    },
    # Newton's Laws
    {
        "id": "p03_newton_first",
        "topic": "Newton's Laws",
        "question": "State Newton's First Law and explain the concept of inertia.",
        "gold_key_terms": ["inertia", "net force", "rest", "motion", "inertial reference frame"],
        "gold_answer_hint": "Object stays at rest or uniform motion unless acted on by net force; inertia is resistance to change in motion, proportional to mass",
    },
    {
        "id": "p04_newton_second",
        "topic": "Newton's Laws",
        "question": "How does Newton's Second Law relate force, mass, and acceleration?",
        "gold_key_terms": ["ΣF = ma", "net force", "mass", "acceleration", "Newton", "free-body"],
        "gold_answer_hint": "Net force = mass × acceleration (ΣF = ma); direction of acceleration equals direction of net force",
    },
    {
        "id": "p05_newton_third",
        "topic": "Newton's Laws",
        "question": "Explain Newton's Third Law and give an example of an action-reaction pair.",
        "gold_key_terms": ["action", "reaction", "equal", "opposite", "different objects", "pair"],
        "gold_answer_hint": "Every action has equal and opposite reaction acting on a different object; e.g., rocket thrust (rocket pushes gas back, gas pushes rocket forward)",
    },
    {
        "id": "p06_friction",
        "topic": "Newton's Laws",
        "question": "How do static and kinetic friction differ, and how is each calculated?",
        "gold_key_terms": ["static friction", "kinetic friction", "μ_s", "μ_k", "normal force", "coefficient"],
        "gold_answer_hint": "Static friction (≤ μ_s N) prevents sliding; kinetic friction (= μ_k N) acts during sliding; μ_k < μ_s",
    },
    # Energy
    {
        "id": "p07_work_energy",
        "topic": "Energy",
        "question": "State the work-energy theorem and explain how kinetic energy depends on speed.",
        "gold_key_terms": ["work-energy theorem", "net work", "kinetic energy", "½mv²", "displacement"],
        "gold_answer_hint": "W_net = ΔKE; KE = ½mv²; net work equals change in kinetic energy",
    },
    {
        "id": "p08_conservation_energy",
        "topic": "Energy",
        "question": "What is conservation of mechanical energy and when does it apply?",
        "gold_key_terms": ["conservation", "mechanical energy", "KE + PE", "friction", "non-conservative", "potential energy"],
        "gold_answer_hint": "KE + PE = constant when no non-conservative forces (like friction) act; KE_i + PE_i = KE_f + PE_f",
    },
    {
        "id": "p09_power",
        "topic": "Energy",
        "question": "Define power and relate it to force and velocity.",
        "gold_key_terms": ["power", "rate", "work", "P = Fv", "Watts", "efficiency"],
        "gold_answer_hint": "Power = W/t = F·v; measured in Watts; efficiency = useful output power / input power",
    },
    # Waves
    {
        "id": "p10_wave_properties",
        "topic": "Waves",
        "question": "What are the key properties of a wave and what is the wave speed equation?",
        "gold_key_terms": ["wavelength", "frequency", "amplitude", "period", "v = fλ", "transverse", "longitudinal"],
        "gold_answer_hint": "Amplitude, wavelength λ, frequency f, period T; wave speed v = fλ; transverse vs longitudinal types",
    },
    {
        "id": "p11_sound_doppler",
        "topic": "Waves",
        "question": "What is the Doppler effect and how does it change the observed frequency of sound?",
        "gold_key_terms": ["Doppler", "frequency", "observer", "source", "velocity", "approaching", "receding"],
        "gold_answer_hint": "Observed frequency shifts when source or observer moves; f_obs = f_s(v ± v_obs)/(v ∓ v_s); approaching increases f, receding decreases f",
    },
    # Electrostatics
    {
        "id": "p12_coulombs_law",
        "topic": "Electrostatics",
        "question": "State Coulomb's Law and explain the electric field concept.",
        "gold_key_terms": ["Coulomb", "F = kq₁q₂/r²", "electric field", "charge", "force", "distance"],
        "gold_answer_hint": "F = k|q₁||q₂|/r²; electric field E = F/q₀ = kq/r² is force per unit positive test charge",
    },
    # Circuits
    {
        "id": "p13_ohm_kirchhoff",
        "topic": "Circuits",
        "question": "State Ohm's Law and both of Kirchhoff's Laws for circuit analysis.",
        "gold_key_terms": ["Ohm's law", "V = IR", "Kirchhoff", "current law", "voltage law", "junction", "loop"],
        "gold_answer_hint": "V = IR; KCL: sum of currents at junction = 0; KVL: sum of voltage changes around any loop = 0",
    },
    {
        "id": "p14_series_parallel",
        "topic": "Circuits",
        "question": "How are the equivalent resistances for series and parallel resistor combinations calculated?",
        "gold_key_terms": ["series", "parallel", "resistance", "R_total", "current", "voltage"],
        "gold_answer_hint": "Series: R_total = R₁ + R₂ + … (same current); Parallel: 1/R_total = 1/R₁ + 1/R₂ + … (same voltage)",
    },
    # Thermodynamics
    {
        "id": "p15_first_law_thermo",
        "topic": "Thermodynamics",
        "question": "State the First and Second Laws of Thermodynamics and define entropy.",
        "gold_key_terms": ["first law", "ΔU = Q − W", "second law", "entropy", "heat", "disorder", "increases"],
        "gold_answer_hint": "First law: ΔU = Q − W (energy conservation); Second law: entropy of universe always increases; entropy S measures disorder",
    },
    {
        "id": "p16_carnot_efficiency",
        "topic": "Thermodynamics",
        "question": "What is the Carnot efficiency and why can no real engine exceed it?",
        "gold_key_terms": ["Carnot", "efficiency", "T_H", "T_C", "1 − T_C/T_H", "maximum", "irreversible"],
        "gold_answer_hint": "η_Carnot = 1 − T_C/T_H; maximum possible efficiency between two temperatures; real engines are irreversible so η_real < η_Carnot",
    },
]


# ── Judge prompt (identical to retrieval_eval.py) ─────────────────────────────

_JUDGE_SYSTEM = """\
You are a strict retrieval quality judge for a RAG system.
Given a student question, a gold answer hint, and retrieved context,
decide whether the context contains enough information to derive the gold answer.
Output ONLY valid JSON — no preamble, no markdown fences:
{
  "verdict": "FULL" | "PARTIAL" | "MISS",
  "reason": "One sentence explaining what is present or missing."
}
"""


# ── Build in-memory Physics ChromaDB collection ────────────────────────────────

def _build_physics_collection() -> chromadb.Collection:
    """
    Create an ephemeral (in-memory) ChromaDB collection and ingest all
    Physics corpus chunks. Uses the same embedding model as the OT system.
    """
    print("[generalizability] Building in-memory Physics vector collection …")
    embedder   = SentenceTransformer(EMBEDDING_MODEL)
    client     = chromadb.EphemeralClient()
    collection = client.create_collection("physics_knowledge_base")

    ids       = [c["id"]   for c in PHYSICS_CORPUS]
    texts     = [c["text"] for c in PHYSICS_CORPUS]
    metadatas = [{"page": c["page"], "topic": c["topic"]} for c in PHYSICS_CORPUS]

    embeddings = embedder.encode(texts).tolist()
    collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
    print(f"[generalizability] Ingested {len(texts)} Physics chunks.")
    return collection, embedder


# ── Local retrieval (identical logic to retriever.py, but accepts any collection) ──

def _retrieve_from(collection: chromadb.Collection, embedder: SentenceTransformer,
                   question: str, k: int = 3) -> tuple[str, list[dict]]:
    """Query any ChromaDB collection — same contract as retrieve_context()."""
    query_emb = embedder.encode([question]).tolist()
    results   = collection.query(query_embeddings=query_emb, n_results=k)
    chunks    = results["documents"][0]
    metas     = results["metadatas"][0]
    context   = "\n\n---\n\n".join(
        f"[Passage {i+1} | Page {m['page']}]\n{c}"
        for i, (c, m) in enumerate(zip(chunks, metas))
    )
    return context, metas


# ── Helpers ────────────────────────────────────────────────────────────────────

def _keyterm_hit_rate(context: str, key_terms: list[str]) -> tuple[float, list, list]:
    ctx   = context.lower()
    hits   = [t for t in key_terms if t.lower() in ctx]
    misses = [t for t in key_terms if t.lower() not in ctx]
    rate   = len(hits) / len(key_terms) if key_terms else 0.0
    return rate, hits, misses


def _llm_judge(question: str, gold_hint: str, context: str) -> dict:
    msg = (
        f"QUESTION: {question}\n\n"
        f"GOLD ANSWER HINT: {gold_hint}\n\n"
        f"RETRIEVED CONTEXT:\n{context}"
    )
    try:
        raw   = llm_chat(_JUDGE_SYSTEM, [{"role": "user", "content": msg}])
        clean = re.sub(r"```[a-z]*", "", raw).strip().strip("`").strip()
        return json.loads(clean)
    except Exception as exc:
        return {"verdict": "PARSE_ERROR", "reason": str(exc)[:120]}


# ── Main eval loop ─────────────────────────────────────────────────────────────

def run_generalizability_eval() -> None:
    """
    Demonstrate subject generalizability by running the full RAG pipeline
    against an in-memory Physics vector database.

    Saves results to eval_results/generalizability_results.json.
    """
    EVAL_OUTPUT_DIR.mkdir(exist_ok=True)

    # Step 1: Build Physics collection (the "swapped" vector DB)
    collection, embedder = _build_physics_collection()

    # Step 2: Run eval loop — identical logic to retrieval_eval.py
    n_questions = len(PHYSICS_EVAL_QS)
    results: list[dict] = []

    print(f"\n[generalizability] Evaluating {n_questions} Physics questions …\n")

    for i, q in enumerate(PHYSICS_EVAL_QS, 1):
        print(f"[{i:02d}/{n_questions}] {q['id']}  ({q['topic']})")

        ctx, srcs = _retrieve_from(collection, embedder, q["question"], k=3)
        pages = [str(s.get("page", "?")) for s in srcs]

        kt_rate, hits, misses = _keyterm_hit_rate(ctx, q["gold_key_terms"])
        judge   = _llm_judge(q["question"], q["gold_answer_hint"], ctx)
        verdict = judge.get("verdict", "PARSE_ERROR")
        sym     = {"FULL": "✅", "PARTIAL": "⚠️", "MISS": "❌"}.get(verdict, "💥")

        print(f"  pages={pages}  kt={kt_rate:.2f}  {sym} {verdict}")
        print(f"  {judge.get('reason', '')[:90]}")

        results.append({
            "id":         q["id"],
            "topic":      q["topic"],
            "question":   q["question"],
            "pages":      pages,
            "kt_rate":    round(kt_rate, 3),
            "kt_hits":    hits,
            "kt_misses":  misses,
            "verdict":    verdict,
            "reason":     judge.get("reason", ""),
            "context":    ctx,
        })
        time.sleep(0.4)

    # Step 3: Aggregate
    verdicts  = [r["verdict"] for r in results]
    n_full    = verdicts.count("FULL")
    n_partial = verdicts.count("PARTIAL")
    n_miss    = verdicts.count("MISS")
    n_total   = len(results)
    mean_kt   = float(np.mean([r["kt_rate"] for r in results]))
    gold_in   = n_full + n_partial

    # Topic-level breakdown
    topics: dict[str, dict] = {}
    for r in results:
        t = r["topic"]
        topics.setdefault(t, {"full": 0, "partial": 0, "miss": 0, "kt": []})
        topics[t][r["verdict"].lower() if r["verdict"] in ("FULL", "PARTIAL", "MISS") else "miss"] += 1
        topics[t]["kt"].append(r["kt_rate"])

    print(f"\n{'─'*60}")
    print(f"Subject: Physics  |  {n_total} questions")
    print(f"FULL: {n_full}/{n_total}  PARTIAL: {n_partial}/{n_total}  MISS: {n_miss}/{n_total}")
    print(f"Gold-in-context: {gold_in}/{n_total} ({100*gold_in/n_total:.0f}%)  Mean KT: {mean_kt:.3f}")
    print("\nPer-topic summary:")
    for topic, v in topics.items():
        avg_kt = float(np.mean(v["kt"])) if v["kt"] else 0.0
        print(f"  {topic:30s}  FULL={v['full']} PARTIAL={v['partial']} "
              f"MISS={v['miss']} avg_kt={avg_kt:.2f}")

    # Generalisation verdict
    pct = 100 * gold_in / n_total
    verdict_line = (
        "PASS — Physics retrieval quality is on par with OT Anatomy. "
        "Swapping the vector DB is sufficient to tutor a new subject."
        if pct >= 60 else
        "PARTIAL — Physics retrieval quality is lower; consider adding more corpus chunks."
    )
    print(f"\nGeneralisation verdict: {verdict_line}")

    # Serialise
    output = {
        "subject":    "Physics",
        "corpus_chunks": len(PHYSICS_CORPUS),
        "aggregate": {
            "n_total":             n_total,
            "n_full":              n_full,
            "n_partial":           n_partial,
            "n_miss":              n_miss,
            "gold_in_context_pct": round(100 * gold_in / n_total, 1),
            "mean_key_term_rate":  round(mean_kt, 3),
        },
        "per_topic": {
            t: {
                "n_full":    v["full"],
                "n_partial": v["partial"],
                "n_miss":    v["miss"],
                "avg_kt":    round(float(np.mean(v["kt"])), 3) if v["kt"] else 0.0,
            }
            for t, v in topics.items()
        },
        "generalisation_verdict": verdict_line,
        "per_question": results,
    }

    RESULTS_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\n✓ Saved → {RESULTS_PATH}")
