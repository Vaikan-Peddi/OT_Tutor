"""
eval/retrieval_eval.py — 40-question retrieval quality evaluation.
All questions are Occupational Therapy–focused anatomy questions
drawn from: OpenStax Anatomy & Physiology 2e (OpenStax, 2022).
"""

import json
import re
import time

import numpy as np

from src.retriever import retrieve_context
from src.llm import llm_chat
from src.config import EVAL_OUTPUT_DIR

RETRIEVAL_EVAL_QS = [
    # ── Ch. 9: Joints ─────────────────────────────────────────────────────────
    {
        "id": "r01_glenohumeral",
        "chapter": "Ch. 9 – Joints",
        "question": "What type of joint is the glenohumeral joint and what movements does it allow?",
        "gold_key_terms": ["glenohumeral", "ball and socket", "flexion", "abduction", "rotation", "synovial"],
        "gold_answer_hint": "Ball-and-socket synovial joint; allows flexion, extension, abduction, adduction, and rotation",
    },
    {
        "id": "r02_carpal_tunnel",
        "chapter": "Ch. 9 – Joints",
        "question": "What passes through the carpal tunnel and what structure is compressed in carpal tunnel syndrome?",
        "gold_key_terms": ["carpal tunnel", "median nerve", "flexor tendons", "transverse carpal ligament", "CTS"],
        "gold_answer_hint": "Median nerve and 9 flexor tendons pass through; median nerve is compressed in CTS",
    },
    {
        "id": "r03_elbow_joint",
        "chapter": "Ch. 9 – Joints",
        "question": "What bones form the elbow joint and what movements does it permit?",
        "gold_key_terms": ["humerus", "radius", "ulna", "hinge", "flexion", "extension", "pronation", "supination"],
        "gold_answer_hint": "Humerus, radius, ulna; hinge joint permitting flexion/extension; proximal radioulnar joint allows pronation/supination",
    },
    {
        "id": "r04_synovial_joint_components",
        "chapter": "Ch. 9 – Joints",
        "question": "What are the structural components of a synovial joint and what is the role of synovial fluid?",
        "gold_key_terms": ["synovial fluid", "articular cartilage", "joint capsule", "synovial membrane", "lubrication"],
        "gold_answer_hint": "Articular cartilage, joint capsule, synovial membrane, synovial fluid; fluid lubricates and nourishes cartilage",
    },
    {
        "id": "r05_wrist_joint",
        "chapter": "Ch. 9 – Joints",
        "question": "What type of joint is the radiocarpal (wrist) joint and what movements does it allow?",
        "gold_key_terms": ["radiocarpal", "condyloid", "flexion", "extension", "radial deviation", "ulnar deviation"],
        "gold_answer_hint": "Condyloid synovial joint; flexion, extension, radial and ulnar deviation, circumduction",
    },

    # ── Ch. 11: Muscular System ───────────────────────────────────────────────
    {
        "id": "r06_rotator_cuff",
        "chapter": "Ch. 11 – Muscular",
        "question": "Which muscles make up the rotator cuff and what is their shared function?",
        "gold_key_terms": ["supraspinatus", "infraspinatus", "teres minor", "subscapularis", "glenohumeral", "stabilize"],
        "gold_answer_hint": "SITS muscles (supraspinatus, infraspinatus, teres minor, subscapularis) stabilise the glenohumeral joint",
    },
    {
        "id": "r07_thenar_muscles",
        "chapter": "Ch. 11 – Muscular",
        "question": "What are the thenar muscles and what movements do they produce at the thumb?",
        "gold_key_terms": ["thenar", "abductor pollicis", "opponens pollicis", "flexor pollicis brevis", "opposition"],
        "gold_answer_hint": "Thenar eminence: abductor pollicis brevis, flexor pollicis brevis, opponens pollicis; enable thumb opposition",
    },
    {
        "id": "r08_wrist_extensors",
        "chapter": "Ch. 11 – Muscular",
        "question": "Which muscles extend the wrist and what nerve innervates them?",
        "gold_key_terms": ["extensor carpi radialis", "extensor carpi ulnaris", "radial nerve", "posterior interosseous"],
        "gold_answer_hint": "ECRL, ECRB, ECU innervated by the radial nerve / posterior interosseous nerve",
    },
    {
        "id": "r09_intrinsic_hand",
        "chapter": "Ch. 11 – Muscular",
        "question": "What are the intrinsic muscles of the hand and how do they contribute to fine motor tasks?",
        "gold_key_terms": ["lumbricals", "interossei", "thenar", "hypothenar", "finger", "opposition", "abduction"],
        "gold_answer_hint": "Lumbricals, dorsal/palmar interossei, thenar and hypothenar groups enable fine pinch, grip, and opposition",
    },
    {
        "id": "r10_biceps_brachii",
        "chapter": "Ch. 11 – Muscular",
        "question": "What are the actions and innervation of the biceps brachii, and why is it important in ADL performance?",
        "gold_key_terms": ["biceps brachii", "flexion", "supination", "musculocutaneous nerve", "elbow", "ADL"],
        "gold_answer_hint": "Flexes elbow and supinates forearm; musculocutaneous nerve (C5–C6); critical for lifting and feeding",
    },
    {
        "id": "r11_extrinsic_finger_flexors",
        "chapter": "Ch. 11 – Muscular",
        "question": "What is the difference between flexor digitorum superficialis and flexor digitorum profundus in function?",
        "gold_key_terms": ["flexor digitorum superficialis", "flexor digitorum profundus", "middle phalanx", "distal phalanx", "grip"],
        "gold_answer_hint": "FDS flexes middle phalanx (PIP); FDP flexes distal phalanx (DIP); both contribute to power grip",
    },
    {
        "id": "r12_deltoid",
        "chapter": "Ch. 11 – Muscular",
        "question": "What are the three parts of the deltoid muscle, their actions, and their innervation?",
        "gold_key_terms": ["deltoid", "anterior", "middle", "posterior", "abduction", "axillary nerve", "C5"],
        "gold_answer_hint": "Anterior flexes/medially rotates, middle abducts, posterior extends/laterally rotates shoulder; all innervated by axillary nerve (C5–C6)",
    },
    {
        "id": "r13_pronator_teres",
        "chapter": "Ch. 11 – Muscular",
        "question": "What is the action of pronator teres and why is it clinically relevant in OT forearm positioning?",
        "gold_key_terms": ["pronator teres", "pronation", "median nerve", "forearm", "humerus", "ulna"],
        "gold_answer_hint": "Pronates the forearm; innervated by median nerve; impairment affects tasks requiring forearm rotation (writing, typing)",
    },
    {
        "id": "r14_hypothenar_muscles",
        "chapter": "Ch. 11 – Muscular",
        "question": "What muscles form the hypothenar eminence and what movements do they produce?",
        "gold_key_terms": ["hypothenar", "abductor digiti minimi", "flexor digiti minimi", "opponens digiti minimi", "little finger"],
        "gold_answer_hint": "Abductor digiti minimi, flexor digiti minimi brevis, opponens digiti minimi; move the little finger",
    },
    {
        "id": "r15_muscle_fiber_types",
        "chapter": "Ch. 11 – Muscular",
        "question": "How do slow-twitch (Type I) and fast-twitch (Type II) muscle fibers differ in fatigue resistance and OT relevance?",
        "gold_key_terms": ["slow twitch", "fast twitch", "Type I", "Type II", "fatigue", "oxidative", "glycolytic"],
        "gold_answer_hint": "Type I: fatigue-resistant, oxidative, postural endurance; Type II: powerful but fatigue quickly, used in rapid gripping",
    },

    # ── Ch. 13: Peripheral Nervous System ────────────────────────────────────
    {
        "id": "r16_ulnar_nerve",
        "chapter": "Ch. 13 – PNS",
        "question": "What is the function of the ulnar nerve and what deficits arise from its injury?",
        "gold_key_terms": ["ulnar nerve", "flexor carpi ulnaris", "intrinsic", "C8", "T1", "claw hand"],
        "gold_answer_hint": "Innervates FCU, medial FDP, most intrinsic hand muscles; injury causes claw hand and loss of fine pinch",
    },
    {
        "id": "r17_radial_nerve_palsy",
        "chapter": "Ch. 13 – PNS",
        "question": "What happens clinically when the radial nerve is damaged at the spiral groove of the humerus?",
        "gold_key_terms": ["wrist drop", "radial nerve", "extensor", "humerus", "spiral groove", "posterior interosseous"],
        "gold_answer_hint": "Wrist drop from loss of wrist and finger extensors; no triceps involvement at this level",
    },
    {
        "id": "r18_median_nerve",
        "chapter": "Ch. 13 – PNS",
        "question": "Which structures does the median nerve innervate in the hand, and what is the LOAF mnemonic?",
        "gold_key_terms": ["median nerve", "thenar", "first two lumbricals", "carpal tunnel", "LOAF", "opposition"],
        "gold_answer_hint": "LOAF: Lumbricals 1–2, Opponens pollicis, Abductor pollicis brevis, Flexor pollicis brevis",
    },
    {
        "id": "r19_brachial_plexus",
        "chapter": "Ch. 13 – PNS",
        "question": "What are the five terminal branches of the brachial plexus and what do they innervate?",
        "gold_key_terms": ["musculocutaneous", "axillary", "radial", "median", "ulnar", "brachial plexus"],
        "gold_answer_hint": "Musculocutaneous (biceps), axillary (deltoid), radial (extensors), median (thenar/LOAF), ulnar (intrinsics)",
    },
    {
        "id": "r20_autonomic_vs_somatic",
        "chapter": "Ch. 13 – PNS",
        "question": "How does the somatic nervous system differ from the autonomic nervous system in terms of motor control?",
        "gold_key_terms": ["somatic", "autonomic", "voluntary", "involuntary", "skeletal muscle", "smooth muscle", "effector"],
        "gold_answer_hint": "Somatic: voluntary control of skeletal muscle (one neuron); ANS: involuntary, two-neuron chain to smooth/cardiac muscle",
    },
    {
        "id": "r21_axillary_nerve",
        "chapter": "Ch. 13 – PNS",
        "question": "What does the axillary nerve innervate and what injury commonly damages it?",
        "gold_key_terms": ["axillary nerve", "deltoid", "teres minor", "C5", "shoulder dislocation", "surgical neck"],
        "gold_answer_hint": "Innervates deltoid and teres minor (C5–C6); damaged in shoulder dislocation or surgical neck fracture of humerus",
    },
    {
        "id": "r22_sensory_receptors_hand",
        "chapter": "Ch. 13 – PNS",
        "question": "What are the major cutaneous mechanoreceptors in the hand and what do they detect?",
        "gold_key_terms": ["Meissner", "Pacinian", "Merkel", "Ruffini", "tactile", "vibration", "pressure", "stretch"],
        "gold_answer_hint": "Meissner (light touch/texture), Pacinian (vibration), Merkel (sustained pressure), Ruffini (skin stretch)",
    },

    # ── Ch. 14: Brain & CNS ───────────────────────────────────────────────────
    {
        "id": "r23_cerebellum",
        "chapter": "Ch. 14 – Brain",
        "question": "What is the primary function of the cerebellum and what happens when it is damaged?",
        "gold_key_terms": ["cerebellum", "coordination", "balance", "ataxia", "posture", "motor"],
        "gold_answer_hint": "Coordinates voluntary movement, balance, and posture; damage causes ataxia and dysmetria",
    },
    {
        "id": "r24_corticospinal_tract",
        "chapter": "Ch. 14 – Brain",
        "question": "What is the role of the corticospinal tract in voluntary movement and where does it decussate?",
        "gold_key_terms": ["corticospinal", "motor cortex", "pyramidal", "decussation", "medulla", "voluntary"],
        "gold_answer_hint": "Primary descending motor pathway; decussates in medulla; carries voluntary motor commands to spinal motor neurons",
    },
    {
        "id": "r25_basal_ganglia",
        "chapter": "Ch. 14 – Brain",
        "question": "How do the basal ganglia contribute to motor control and what disorder results from dopamine depletion there?",
        "gold_key_terms": ["basal ganglia", "striatum", "dopamine", "Parkinson", "caudate", "putamen", "motor control"],
        "gold_answer_hint": "Modulate movement initiation/suppression; dopamine depletion → Parkinson's disease (resting tremor, bradykinesia)",
    },
    {
        "id": "r26_primary_motor_cortex",
        "chapter": "Ch. 14 – Brain",
        "question": "How is the primary motor cortex organised and what area is disproportionately large for OT relevance?",
        "gold_key_terms": ["motor cortex", "homunculus", "somatotopic", "hand", "face", "precentral gyrus"],
        "gold_answer_hint": "Somatotopic map (motor homunculus) on precentral gyrus; hand and face areas are disproportionately large",
    },
    {
        "id": "r27_frontal_lobe_executive",
        "chapter": "Ch. 14 – Brain",
        "question": "What are the executive functions attributed to the prefrontal cortex and how do they relate to ADL performance?",
        "gold_key_terms": ["prefrontal cortex", "executive function", "planning", "working memory", "inhibition", "ADL"],
        "gold_answer_hint": "Planning, working memory, inhibition, decision-making; prefrontal damage impairs sequencing of ADL tasks",
    },
    {
        "id": "r28_thalamus",
        "chapter": "Ch. 14 – Brain",
        "question": "What is the role of the thalamus as a relay station for sensory and motor pathways?",
        "gold_key_terms": ["thalamus", "relay", "sensory", "VPL", "VPM", "motor", "cortex"],
        "gold_answer_hint": "Relays sensory signals (VPL/VPM nuclei) to somatosensory cortex; also relays cerebellar/basal ganglia output to motor cortex",
    },

    # ── Ch. 16: Neurological Disorders & Spinal Cord ─────────────────────────
    {
        "id": "r29_upper_motor_neuron",
        "chapter": "Ch. 16 – Neurological",
        "question": "What are the clinical signs of an upper motor neuron lesion?",
        "gold_key_terms": ["upper motor neuron", "spasticity", "hyperreflexia", "Babinski", "weakness"],
        "gold_answer_hint": "Spasticity, hyperreflexia, positive Babinski sign, weakness without atrophy (early)",
    },
    {
        "id": "r30_lower_motor_neuron",
        "chapter": "Ch. 16 – Neurological",
        "question": "How do lower motor neuron lesion signs differ from upper motor neuron lesion signs?",
        "gold_key_terms": ["lower motor neuron", "flaccidity", "atrophy", "fasciculations", "hyporeflexia"],
        "gold_answer_hint": "Flaccid paralysis, muscle atrophy, fasciculations, hyporeflexia/areflexia — direct neuromuscular disruption",
    },
    {
        "id": "r31_dermatomes",
        "chapter": "Ch. 16 – Neurological",
        "question": "What is a dermatome and why is it clinically relevant for OT sensory assessment?",
        "gold_key_terms": ["dermatome", "spinal nerve", "sensory", "C6", "C7", "T1"],
        "gold_answer_hint": "Skin area innervated by a single spinal nerve root; dermatome mapping identifies spinal level of nerve injury",
    },
    {
        "id": "r32_spinal_tracts",
        "chapter": "Ch. 16 – Neurological",
        "question": "What are the main ascending and descending spinal cord tracts and their respective functions?",
        "gold_key_terms": ["dorsal column", "spinothalamic", "corticospinal", "sensory", "motor", "decussation"],
        "gold_answer_hint": "Dorsal column (fine touch/proprioception), spinothalamic (pain/temp), corticospinal (voluntary motor)",
    },
    {
        "id": "r33_spinal_cord_levels_UE",
        "chapter": "Ch. 16 – Neurological",
        "question": "Which spinal cord levels (myotomes) control key upper extremity movements relevant to OT?",
        "gold_key_terms": ["C5", "C6", "C7", "C8", "T1", "elbow", "wrist", "grip", "myotome"],
        "gold_answer_hint": "C5 shoulder abduction, C6 wrist extension, C7 elbow extension, C8 finger flexion, T1 finger abduction",
    },
    {
        "id": "r34_proprioception_pathway",
        "chapter": "Ch. 16 – Neurological",
        "question": "Describe the pathway for proprioceptive signals from the hand to the cortex.",
        "gold_key_terms": ["proprioception", "dorsal column", "medial lemniscus", "thalamus", "somatosensory cortex", "ipsilateral"],
        "gold_answer_hint": "Receptors → dorsal column (ipsilateral) → medulla decussation → medial lemniscus → VPL thalamus → somatosensory cortex",
    },

    # ── Ch. 7–8: Skeletal System / Bone ──────────────────────────────────────
    {
        "id": "r35_bone_remodeling",
        "chapter": "Ch. 7 – Skeletal",
        "question": "What are osteoblasts and osteoclasts, and how does their balance affect bone remodeling?",
        "gold_key_terms": ["osteoblast", "osteoclast", "remodeling", "bone formation", "resorption", "osteoporosis"],
        "gold_answer_hint": "Osteoblasts form bone; osteoclasts resorb it; imbalance (excess resorption) leads to osteoporosis",
    },
    {
        "id": "r36_colles_fracture",
        "chapter": "Ch. 7 – Skeletal",
        "question": "What is a Colles fracture and why is it common in older adults with osteoporosis?",
        "gold_key_terms": ["Colles fracture", "distal radius", "fall on outstretched hand", "FOOSH", "osteoporosis", "dinner fork"],
        "gold_answer_hint": "Fracture of the distal radius with dorsal displacement; common FOOSH injury; osteoporotic bone fractures more easily",
    },
    {
        "id": "r37_phalanges_metacarpals",
        "chapter": "Ch. 8 – Appendicular Skeleton",
        "question": "How are the bones of the hand (phalanges and metacarpals) numbered and named, and what joints do they form?",
        "gold_key_terms": ["metacarpal", "proximal phalanx", "middle phalanx", "distal phalanx", "MCP", "PIP", "DIP"],
        "gold_answer_hint": "Five metacarpals; proximal, middle, distal phalanges (thumb has 2); MCP, PIP, DIP joints",
    },

    # ── Ch. 10 / Ch. 19–20: Cardiovascular & Lymphatics ─────────────────────
    {
        "id": "r38_lymphedema_anatomy",
        "chapter": "Ch. 21 – Lymphatic",
        "question": "What anatomical structures are involved in lymphatic drainage of the upper extremity, and how does their disruption cause lymphedema?",
        "gold_key_terms": ["lymphatic vessels", "axillary lymph nodes", "lymphedema", "interstitial fluid", "thoracic duct"],
        "gold_answer_hint": "Lymph from UE drains through axillary nodes; node removal/damage (e.g., post-mastectomy) causes protein-rich fluid accumulation = lymphedema",
    },

    # ── Ch. 17–18: Endocrine & Integumentary ─────────────────────────────────
    {
        "id": "r39_skin_sensory_OT",
        "chapter": "Ch. 5 – Integumentary",
        "question": "What layers of the skin contain sensory receptors relevant to tactile perception in the hand?",
        "gold_key_terms": ["epidermis", "dermis", "Meissner corpuscle", "Pacinian corpuscle", "free nerve ending", "tactile"],
        "gold_answer_hint": "Meissner corpuscles in dermal papillae (fine touch); Pacinian corpuscles in deep dermis/hypodermis (vibration); free nerve endings throughout (pain/temp)",
    },

    # ── Ch. 25 / Developmental: Neuroplasticity & Rehab ─────────────────────
    {
        "id": "r40_neuroplasticity",
        "chapter": "Ch. 14 – Brain / Rehab",
        "question": "What is neuroplasticity and how does it underpin OT rehabilitation strategies after brain injury?",
        "gold_key_terms": ["neuroplasticity", "synaptic", "reorganization", "cortical map", "rehabilitation", "stroke", "learning"],
        "gold_answer_hint": "Brain's ability to reorganise synaptic connections; task-specific practice drives cortical remapping, forming the basis for OT interventions post-stroke",
    },
]

# ── Judge prompt ──────────────────────────────────────────────────────────────
JUDGE_SYSTEM = """\
You are a strict retrieval quality judge for a medical RAG system.
Given a student question, a gold answer hint, and retrieved context,
decide whether the context contains enough information to derive the gold answer.
Output ONLY valid JSON — no preamble, no markdown fences:
{
  "verdict": "FULL" | "PARTIAL" | "MISS",
  "reason": "One sentence explaining what is present or missing."
}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────
def keyterm_hit_rate(context: str, key_terms: list) -> tuple:
    ctx = context.lower()
    hits   = [t for t in key_terms if t.lower() in ctx]
    misses = [t for t in key_terms if t.lower() not in ctx]
    rate   = len(hits) / len(key_terms) if key_terms else 0.0
    return rate, hits, misses


def llm_judge(question: str, gold_hint: str, context: str) -> dict:
    msg = (
        f"QUESTION: {question}\n\n"
        f"GOLD ANSWER HINT: {gold_hint}\n\n"
        f"RETRIEVED CONTEXT:\n{context}"
    )
    try:
        raw   = llm_chat(JUDGE_SYSTEM, [{"role": "user", "content": msg}])
        clean = re.sub(r"```[a-z]*", "", raw).strip().strip("`").strip()
        return json.loads(clean)
    except Exception as e:
        return {"verdict": "PARSE_ERROR", "reason": str(e)[:120]}


# ── Main eval loop ────────────────────────────────────────────────────────────
def run_retrieval_eval() -> dict:
    EVAL_OUTPUT_DIR.mkdir(exist_ok=True)
    n_questions = len(RETRIEVAL_EVAL_QS)
    results = []

    for i, q in enumerate(RETRIEVAL_EVAL_QS, 1):
        print(f"[{i:02d}/{n_questions}] {q['id']}")
        ctx, srcs = retrieve_context(q["question"], k=3)
        pages = [s.get("page", "?") for s in srcs]
        kt_rate, hits, misses = keyterm_hit_rate(ctx, q["gold_key_terms"])
        judge   = llm_judge(q["question"], q["gold_answer_hint"], ctx)
        verdict = judge.get("verdict", "PARSE_ERROR")
        sym     = {"FULL": "✅", "PARTIAL": "⚠️", "MISS": "❌"}.get(verdict, "💥")
        print(f"  pages={pages}  kt={kt_rate:.2f}  {sym} {verdict}")
        print(f"  {judge.get('reason', '')[:90]}")
        results.append({
            "id":         q["id"],
            "chapter":    q["chapter"],
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

    # ── Aggregate metrics ─────────────────────────────────────────────────────
    verdicts   = [r["verdict"] for r in results]
    n_full     = verdicts.count("FULL")
    n_partial  = verdicts.count("PARTIAL")
    n_miss     = verdicts.count("MISS")
    n_total    = len(results)
    mean_kt    = float(np.mean([r["kt_rate"] for r in results]))
    gold_in    = n_full + n_partial

    print(f"\n{'─'*55}")
    print(f"FULL: {n_full}/{n_total}  PARTIAL: {n_partial}/{n_total}  MISS: {n_miss}/{n_total}")
    print(f"Gold-in-context: {gold_in}/{n_total} ({100*gold_in/n_total:.0f}%)  "
          f"Mean KT: {mean_kt:.3f}")

    # ── Chapter-level breakdown ───────────────────────────────────────────────
    chapters = {}
    for r in results:
        ch = r["chapter"]
        chapters.setdefault(ch, {"full": 0, "partial": 0, "miss": 0, "kt": []})
        chapters[ch][r["verdict"].lower() if r["verdict"] in ("FULL","PARTIAL","MISS") else "miss"] += 1
        chapters[ch]["kt"].append(r["kt_rate"])

    print("\nPer-chapter summary:")
    for ch, v in chapters.items():
        avg_kt = float(np.mean(v["kt"])) if v["kt"] else 0.0
        print(f"  {ch:35s} FULL={v['full']} PARTIAL={v['partial']} "
              f"MISS={v['miss']} avg_kt={avg_kt:.2f}")

    # ── Serialise ─────────────────────────────────────────────────────────────
    out = {
        "aggregate": {
            "n_total":              n_total,
            "n_full":               n_full,
            "n_partial":            n_partial,
            "n_miss":               n_miss,
            "gold_in_context_pct":  round(100 * gold_in / n_total, 1),
            "mean_key_term_rate":   round(mean_kt, 3),
        },
        "per_chapter": {
            ch: {
                "n_full":    v["full"],
                "n_partial": v["partial"],
                "n_miss":    v["miss"],
                "avg_kt":    round(float(np.mean(v["kt"])), 3) if v["kt"] else 0.0,
            }
            for ch, v in chapters.items()
        },
        "per_question": results,
    }

    out_path = EVAL_OUTPUT_DIR / "retrieval_quality_results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n✓ Saved to {out_path}")
    return out