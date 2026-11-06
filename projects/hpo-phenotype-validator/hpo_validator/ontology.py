"""Read the HPO OBO subset needed for identifiers, synonyms and asserted ancestry."""

from collections import defaultdict, deque
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re

ID_PATTERN = re.compile(r"HP:\d{7}\Z")


def unescape(value: str) -> str:
    escapes = {"n": "\n", "t": "\t", "W": " "}
    return re.sub(r"\\(.)", lambda m: escapes.get(m[1], m[1]), value)


def scalar_value(value: str) -> str:
    """Remove OBO comments/modifiers while preserving quoted and escaped literals."""
    quoted = escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted and char in "!{":
            return value[:index].rstrip()
    return value


@dataclass
class Term:
    id: str
    name: str
    parents: set[str] = field(default_factory=set)
    alt_ids: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    obsolete: bool = False
    replacements: list[str] = field(default_factory=list)
    consider: list[str] = field(default_factory=list)


class Ontology:
    def __init__(self, terms: dict[str, Term], version: str, sha256: str):
        self.terms = terms
        self.version = version
        self.sha256 = sha256
        self.aliases: dict[str, str] = {}
        self._ancestry: dict[str, frozenset[str]] = {}
        for term in terms.values():
            for alias in term.alt_ids:
                if (alias in terms and not terms[alias].obsolete) or alias in self.aliases:
                    raise ValueError(f"Conflicting alternative ID: {alias}")
                self.aliases[alias] = term.id
        # Validate the entire active graph once; only cache ancestry requested by a list.
        active = {k: t for k, t in terms.items() if not t.obsolete}
        degree = {}
        children = defaultdict(list)
        for key, term in active.items():
            if any(p not in active for p in term.parents):
                raise ValueError(f"Missing or obsolete parent for {key}")
            degree[key] = len(term.parents)
            for parent in term.parents:
                children[parent].append(key)
        queue = deque(k for k, count in degree.items() if count == 0)
        visited = 0
        while queue:
            visited += 1
            for child in children[queue.popleft()]:
                degree[child] -= 1
                if degree[child] == 0:
                    queue.append(child)
        if visited != len(active):
            raise ValueError("Cycle in is_a graph")

    @classmethod
    def load(cls, path: Path, verify: bool = False) -> "Ontology":
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if verify:
            manifest = json.loads(path.with_name("manifest.json").read_text())
            if manifest["sha256"] != digest:
                raise ValueError("Ontology checksum mismatch")
        terms = {}
        version = ""
        stanza = ""
        fields = defaultdict(list)

        def finish():
            if stanza != "Term":
                return
            key = fields.get("id", [""])[0]
            name = fields.get("name", [""])[0]
            if not ID_PATTERN.fullmatch(key) or not name or key in terms:
                raise ValueError(f"Missing, duplicate or invalid HPO term: {key}")
            synonyms = []
            for value in fields["synonym"]:
                match = re.match(r'"((?:\\.|[^"\\])*)"\s+EXACT\b', value)
                if match:
                    synonyms.append(unescape(match[1]))
            terms[key] = Term(
                key,
                unescape(name),
                {v.split()[0] for v in fields["is_a"]},
                [v.split()[0] for v in fields["alt_id"]],
                synonyms,
                fields.get("is_obsolete", ["false"])[0] == "true",
                [v.split()[0] for v in fields["replaced_by"]],
                [v.split()[0] for v in fields["consider"]],
            )

        for line in raw.decode("utf-8").splitlines():
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                finish()
                stanza, fields = line[1:-1], defaultdict(list)
            elif ": " in line and not line.startswith("!"):
                tag, value = line.split(": ", 1)
                value = scalar_value(value)
                if not stanza and tag == "data-version":
                    version = value
                else:
                    fields[tag].append(value)
        finish()
        if not terms or not version:
            raise ValueError("Ontology needs terms and a data-version header")
        return cls(terms, version, digest)

    def resolve(self, key: str) -> dict:
        original = key
        path = []
        replaced = False
        while key not in path:
            path.append(key)
            if key in self.aliases and key not in self.terms:
                key = self.aliases[key]
                continue
            term = self.terms.get(key)
            if term is None:
                return {"id": None, "status": "unknown", "path": path, "suggestions": []}
            if not term.obsolete:
                status = (
                    "replaced" if replaced else ("alternative" if key != original else "current")
                )
                return {"id": key, "status": status, "path": path, "suggestions": []}
            replaced = True
            if len(term.replacements) != 1:
                return {
                    "id": None,
                    "status": "obsolete_review",
                    "path": path,
                    "suggestions": term.replacements or term.consider,
                }
            key = term.replacements[0]
        return {"id": None, "status": "replacement_cycle", "path": path, "suggestions": []}

    def ancestors(self, key: str) -> frozenset[str]:
        if key not in self._ancestry:
            seen = set()
            pending = list(self.terms[key].parents)
            while pending:
                parent = pending.pop()
                if parent not in seen:
                    seen.add(parent)
                    pending.extend(self.terms[parent].parents)
            self._ancestry[key] = frozenset(seen)
        return self._ancestry[key]

    def is_phenotype(self, key: str) -> bool:
        return "HP:0000118" in self.ancestors(key)
