"""Grade tracker: running course grades from sample syllabus weights, and what it takes to reach a target.

Official grades are only in CampusNet. These scores are the student's own record.
"""
import json
import math

from flask import Blueprint, abort, jsonify, render_template, request, session

from db import get_db, query_all, query_one
from security import login_required

bp = Blueprint("grades", __name__)

# Standard setup every course starts with until the student matches it to the syllabus
SCALE = [("A", 93), ("A-", 90), ("B+", 87), ("B", 83), ("B-", 80), ("C+", 77), ("C", 73), ("C-", 70), ("D+", 67), ("D", 60)]
TARGETS = ["A", "A-", "B+", "B", "B-", "C+", "C"]
STANDARD_SECTIONS = [("Assignments", 40), ("Quizzes", 15), ("Exams", 35), ("Participation", 10)]


def letter(percent, scale=SCALE):
    return next((l for l, cut in scale if percent >= cut - 1e-9), "F")


def ensure_course(sid, code):
    """Every class on the schedule gets the standard sections the first time grades are shown."""
    if query_one("SELECT 1 FROM grade_courses WHERE student_id = ? AND course_code = ?", (sid, code)):
        return
    db = get_db()
    db.execute("INSERT INTO grade_courses (student_id, course_code, customized) VALUES (?, ?, 0)", (sid, code))
    if not query_one("SELECT 1 FROM grade_categories WHERE student_id = ? AND course_code = ?", (sid, code)):
        for pos, (name, weight) in enumerate(STANDARD_SECTIONS):
            db.execute("INSERT INTO grade_categories (student_id, course_code, name, weight, position) VALUES (?, ?, ?, ?, ?)",
                       (sid, code, name, weight, pos))
    db.commit()


def course_setup(sid, code):
    row = query_one("SELECT * FROM grade_courses WHERE student_id = ? AND course_code = ?", (sid, code))
    scale = [tuple(x) for x in json.loads(row["scale"])] if row and row["scale"] else SCALE
    return {"customized": bool(row and row["customized"]), "scale": scale}


def _pct(x):
    return round(x * 100, 1)


def course_summary(sid, code):
    cats = query_all("SELECT * FROM grade_categories WHERE student_id = ? AND course_code = ? ORDER BY position",
                     (sid, code))
    total_weight = sum(c["weight"] for c in cats) or 1
    categories = []
    graded_weight = 0.0
    weighted = 0.0
    locked_in = 0.0     # points already earned toward the final grade, as a fraction of 100
    open_share = 0.0    # share of the final grade still to be earned
    remaining_titles = []
    for c in cats:
        items = query_all("SELECT * FROM grade_items WHERE category_id = ? ORDER BY due_date IS NULL, due_date, id", (c["id"],))
        w = c["weight"] / total_weight
        earned = sum(i["earned"] for i in items if i["earned"] is not None)
        graded_possible = sum(i["possible"] for i in items if i["earned"] is not None)
        all_possible = sum(i["possible"] for i in items) or 1
        remaining = all_possible - graded_possible
        score = earned / graded_possible if graded_possible else None
        if score is not None:
            graded_weight += w
            weighted += w * score
        if items:
            locked_in += w * earned / all_possible
            open_share += w * remaining / all_possible
            remaining_titles += [i["title"] for i in items if i["earned"] is None]
        else:  # nothing recorded yet: the whole category is still to come
            open_share += w
            remaining_titles.append(c["name"])
        categories.append({
            "id": c["id"], "name": c["name"], "weight": c["weight"],
            "score": _pct(score) if score is not None else None,
            "items": [{"id": i["id"], "title": i["title"], "earned": i["earned"], "possible": i["possible"],
                       "due_date": i["due_date"],
                       "percent": _pct(i["earned"] / i["possible"]) if i["earned"] is not None else None}
                      for i in items],
        })
    current = weighted / graded_weight if graded_weight else None
    setup = course_setup(sid, code)
    return {
        "code": code,
        "customized": setup["customized"],
        "scale": setup["scale"],
        "total_weight": sum(c["weight"] for c in cats),
        "current": _pct(current) if current is not None else None,
        "letter": letter(current * 100, setup["scale"]) if current is not None else None,
        "locked_in": _pct(locked_in),          # the grade if every remaining item scored 0
        "best_case": _pct(locked_in + open_share),  # the grade if every remaining item scored 100
        "open_share": _pct(open_share),
        "remaining": remaining_titles,
        "categories": categories,
    }


def need_for(summary, target_letter):
    """The average needed on everything still to come to finish with the target letter."""
    cut = dict(summary["scale"])[target_letter]
    if not summary["remaining"]:
        reached = summary["current"] is not None and summary["current"] >= cut
        return {"state": "done", "reached": reached, "cut": cut}
    need = (cut - summary["locked_in"]) / summary["open_share"] * 100
    if need <= 0:
        return {"state": "secured", "cut": cut}
    if need > 100:
        return {"state": "out_of_reach", "cut": cut, "best": summary["best_case"]}
    return {"state": "needed", "cut": cut, "need": round(need)}


def all_courses(sid):
    """One grade card per class on the schedule."""
    professors = {r["code"]: r["professor"] for r in query_all("SELECT code, professor FROM courses WHERE student_id = ?", (sid,))}
    codes = sorted(professors)
    for code in codes:
        ensure_course(sid, code)
    out = []
    for code in codes:
        s = course_summary(sid, code)
        s["professor"] = professors.get(code, "")
        out.append(s)
    return out


def _item_for(sid, item_id):
    row = query_one(
        """SELECT gi.*, gc.course_code FROM grade_items gi JOIN grade_categories gc ON gc.id = gi.category_id
           WHERE gi.id = ? AND gc.student_id = ?""", (item_id, sid))
    if row is None:
        abort(404, description="That score was already removed.")
    return row


def _number(value, field, allow_empty=False):
    if value in (None, "") and allow_empty:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        abort(400, description=f"Enter a number for {field}.")
    if not math.isfinite(n):
        abort(400, description=f"Enter a number for {field}.")
    if n < 0 or n > 1000:
        abort(400, description=f"Enter a number from 0 to 1000 for {field}.")
    return round(n, 2)


@bp.route("/grades")
@login_required
def index():
    sid = session["student_id"]
    return render_template("grades.html", title="Grades", courses=all_courses(sid), targets=TARGETS,
                           standard={"sections": STANDARD_SECTIONS, "scale": SCALE})


@bp.route("/api/grades/need")
@login_required
def need():
    sid = session["student_id"]
    code = request.args.get("course", "")
    target = request.args.get("target", "B")
    if target not in TARGETS:
        abort(400, description="Choose a target grade.")
    summary = course_summary(sid, code)
    if not summary["categories"]:
        abort(404, description="That course isn't in your grade tracker.")
    return jsonify(need_for(summary, target))


@bp.route("/api/grades/items/<int:item_id>", methods=["PATCH"])
@login_required
def update_item(item_id):
    sid = session["student_id"]
    item = _item_for(sid, item_id)
    data = request.get_json(silent=True) or {}
    earned = _number(data.get("earned"), "the score", allow_empty=True)
    possible = _number(data.get("possible", item["possible"]), "points possible")
    if possible <= 0:
        abort(400, description="Points possible must be more than 0.")
    if earned is not None and earned > possible * 1.5:
        abort(400, description="That score is much higher than the points possible.")
    db = get_db()
    db.execute("UPDATE grade_items SET earned = ?, possible = ? WHERE id = ?", (earned, possible, item_id))
    db.commit()
    return jsonify(course=course_summary(sid, item["course_code"]))


@bp.route("/api/grades/items", methods=["POST"])
@login_required
def add_item():
    sid = session["student_id"]
    data = request.get_json(silent=True) or {}
    cat = query_one("SELECT * FROM grade_categories WHERE id = ? AND student_id = ?", (data.get("category_id"), sid))
    if cat is None:
        abort(404, description="Choose a category.")
    title = " ".join(str(data.get("title", "")).split())[:80]
    if not title:
        abort(400, description="Give the score a name, like Quiz 5.")
    possible = _number(data.get("possible"), "points possible")
    if possible <= 0:
        abort(400, description="Points possible must be more than 0.")
    earned = _number(data.get("earned"), "the score", allow_empty=True)
    db = get_db()
    db.execute("INSERT INTO grade_items (category_id, title, earned, possible) VALUES (?, ?, ?, ?)",
               (cat["id"], title, earned, possible))
    db.commit()
    return jsonify(course=course_summary(sid, cat["course_code"]), message=f"{title} added to {cat['course_code']}")


@bp.route("/api/grades/items/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):
    sid = session["student_id"]
    item = _item_for(sid, item_id)
    db = get_db()
    db.execute("DELETE FROM grade_items WHERE id = ?", (item_id,))
    db.commit()
    return jsonify(course=course_summary(sid, item["course_code"]), message=f"{item['title']} removed")


def _course_or_404(sid, code):
    if not query_one("SELECT 1 FROM courses WHERE student_id = ? AND code = ?", (sid, code)):
        abort(404, description="That class isn't on your schedule.")


@bp.route("/api/grades/<code>/setup", methods=["POST"])
@login_required
def save_setup(code):
    """Save a course's sections (name and weight) and letter scale, as the student set them from the syllabus."""
    sid = session["student_id"]
    _course_or_404(sid, code)
    data = request.get_json(silent=True) or {}
    sections = data.get("sections") or []
    if not isinstance(sections, list) or not all(isinstance(x, dict) for x in sections):
        abort(400, description="Something went wrong with the sections. Refresh the page and try again.")
    if not sections:
        abort(400, description="Keep at least one section.")
    clean = []
    for sec in sections:
        name = " ".join(str(sec.get("name", "")).split())[:40]
        if not name:
            abort(400, description="Every section needs a name.")
        try:
            weight = int(sec.get("weight"))
        except (TypeError, ValueError):
            abort(400, description=f"Give {name} a weight from 1 to 100.")
        if not 1 <= weight <= 100:
            abort(400, description=f"Give {name} a weight from 1 to 100.")
        clean.append((sec.get("id"), name, weight))
    total = sum(w for _, _, w in clean)
    if total != 100:
        abort(400, description=f"The weights add up to {total}%. Make them total 100%.")
    if len({n.lower() for _, n, _ in clean}) != len(clean):
        abort(400, description="Each section needs a different name.")

    scale_in = data.get("scale") or []
    if not isinstance(scale_in, list) or not all(isinstance(x, list) and len(x) == 2 for x in scale_in):
        abort(400, description="Give every letter grade a cutoff.")
    letters = [l for l, _ in SCALE]
    try:
        scale = [(l, float(dict(scale_in)[l])) for l in letters]
    except (KeyError, TypeError, ValueError):
        abort(400, description="Give every letter grade a cutoff.")
    for (l1, c1), (l2, c2) in zip(scale, scale[1:]):
        if not 0 < c2 < c1 <= 100:
            abort(400, description=f"{l1} needs a higher cutoff than {l2}, and every cutoff goes between 0 and 100.")

    db = get_db()
    existing = {r["id"] for r in query_all(
        "SELECT id FROM grade_categories WHERE student_id = ? AND course_code = ?", (sid, code))}
    kept = set()
    for pos, (cid, name, weight) in enumerate(clean):
        if cid in existing:
            db.execute("UPDATE grade_categories SET name = ?, weight = ?, position = ? WHERE id = ?", (name, weight, pos, cid))
            kept.add(cid)
        else:
            db.execute("INSERT INTO grade_categories (student_id, course_code, name, weight, position) VALUES (?, ?, ?, ?, ?)",
                       (sid, code, name, weight, pos))
    for cid in existing - kept:
        db.execute("DELETE FROM grade_items WHERE category_id = ?", (cid,))
        db.execute("DELETE FROM grade_categories WHERE id = ?", (cid,))
    db.execute("""INSERT INTO grade_courses (student_id, course_code, customized, scale) VALUES (?, ?, 1, ?)
                  ON CONFLICT(student_id, course_code) DO UPDATE SET customized = 1, scale = excluded.scale""",
               (sid, code, json.dumps([[l, c] for l, c in scale])))
    db.commit()
    return jsonify(course={**course_summary(sid, code)}, message=f"{code} sections saved")


@bp.route("/api/grades/<code>/reset", methods=["POST"])
@login_required
def reset_setup(code):
    """Go back to the standard sections and scale. Scores in this course are removed."""
    sid = session["student_id"]
    _course_or_404(sid, code)
    db = get_db()
    for r in query_all("SELECT id FROM grade_categories WHERE student_id = ? AND course_code = ?", (sid, code)):
        db.execute("DELETE FROM grade_items WHERE category_id = ?", (r["id"],))
    db.execute("DELETE FROM grade_categories WHERE student_id = ? AND course_code = ?", (sid, code))
    db.execute("DELETE FROM grade_courses WHERE student_id = ? AND course_code = ?", (sid, code))
    db.commit()
    ensure_course(sid, code)
    return jsonify(course=course_summary(sid, code), message=f"{code} is back to the standard sections")
