#!/usr/bin/env python3

import argparse
import csv
import difflib
import os
import re
import sys
import tempfile
import time
import warnings
from collections import defaultdict
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

warnings.filterwarnings("ignore", category=UserWarning)

DEFAULT_IRI = "http://example.org/kr-group11/drinks"

SPECIAL_FILES = {"classes.csv", "properties.csv", "axioms.csv"}

# Properties the CSV files of our repo use. Each one is only added when it is NOT
# already in the base .ttl or in a properties.csv, so the ontology always wins.
# These are modelling choices: change them here (or move them into the .ttl) when the group decides.
DEFAULT_PROPERTIES = [
    # D8 + D10: range Flavour, no domain; drinks get the flavours of their ingredients
    {"name": "hasFlavour", "kind": "object", "range": "Flavour", "chain": "hasIngredient o hasFlavour"},
    # customers.csv
    {"name": "likesIngredient", "kind": "object", "domain": "Person", "range": "Ingredient"},
    {"name": "likesFlavour", "kind": "object", "domain": "Person", "range": "Flavour"},
    {"name": "dislikesFlavour", "kind": "object", "domain": "Person", "range": "Flavour"},
]
DEFAULT_BASE = "KnowledgeBase-Drink.ttl"
DEFAULT_OUT = "KnowledgeBase-Drink-full.ttl"
PREFIXES = {"owl": OWL, "rdf": RDF, "rdfs": RDFS, "xsd": XSD}
INDIVIDUAL_RESERVED = {"category", "name", "types", "close", "label", "comment"}
CHARACTERISTICS = {
    "functional": OWL.FunctionalProperty,
    "inverse_functional": OWL.InverseFunctionalProperty,
    "transitive": OWL.TransitiveProperty,
    "symmetric": OWL.SymmetricProperty,
    "asymmetric": OWL.AsymmetricProperty,
    "reflexive": OWL.ReflexiveProperty,
    "irreflexive": OWL.IrreflexiveProperty,
}
KIND_TYPES = {
    "class": OWL.Class,
    "object": OWL.ObjectProperty,
    "data": OWL.DatatypeProperty,
    "annotation": OWL.AnnotationProperty,
    "individual": OWL.NamedIndividual,
}
RESTRICTION_KW = {"some", "only", "value", "min", "max", "exactly", "self"}


class KBError(Exception):
    pass


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------

class Registry:
    """Knows every name in the ontology and what kind of thing it is."""

    def __init__(self, ns):
        self.ns = ns
        self.kinds = defaultdict(set)      # local name -> {"class", "object", ...}
        self.where = {}                    # (name, kind) -> "file line n"
        self.data_ranges = {}              # data property -> datatype URI

    def declare(self, name, kind, where):
        if (name, kind) in self.where and self.where[(name, kind)] != "base":
            raise KBError(f"'{name}' is defined twice (also in {self.where[(name, kind)]})")
        self.kinds[name].add(kind)
        self.where[(name, kind)] = where

    def load_graph(self, g):
        for kind, t in KIND_TYPES.items():
            for s in g.subjects(RDF.type, t):
                if isinstance(s, URIRef) and str(s).startswith(str(self.ns)):
                    self.declare(str(s)[len(str(self.ns)):], kind, "base")
        for p, r in g.subject_objects(RDFS.range):
            if (p, RDF.type, OWL.DatatypeProperty) in g and str(p).startswith(str(self.ns)):
                self.data_ranges[str(p)[len(str(self.ns)):]] = r

    def uri(self, name, kind, what=None):
        name = clean(name)
        if name.startswith("<") and name.endswith(">"):
            return URIRef(name[1:-1])
        if ":" in name:
            prefix, local = name.split(":", 1)
            if prefix in PREFIXES:
                return PREFIXES[prefix][local]
            raise KBError(f"unknown prefix in '{name}'")
        if kind == "class" and name in ("Thing", "Nothing"):
            return OWL[name]
        kinds = kind if isinstance(kind, tuple) else (kind,)
        if not any(k in self.kinds.get(name, ()) for k in kinds):
            what = what or "/".join(kinds)
            known = [n for n, ks in self.kinds.items() if any(k in ks for k in kinds)]
            close = difflib.get_close_matches(name, known, n=3)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            if name in self.kinds:
                raise KBError(f"'{name}' is a {'/'.join(sorted(self.kinds[name]))}, not a {what}.{hint}")
            raise KBError(f"unknown {what} '{name}'.{hint}")
        return self.ns[name]

    def prop(self, name):
        """Return (uri, 'object'|'data'|'annotation')."""
        name = clean(name)
        if ":" in name and name.split(":", 1)[0] in PREFIXES:
            u = self.uri(name, "object")
            return u, "data" if u in (OWL.topDataProperty, OWL.bottomDataProperty) else "object"
        for k in ("object", "data", "annotation"):
            if k in self.kinds.get(name, ()):
                return self.ns[name], k
        self.uri(name, ("object", "data", "annotation"), "property")  # raises with a hint


def clean(name):
    name = name.strip()
    return name[1:] if name.startswith(":") else name


def split_list(cell):
    return [x.strip() for x in (cell or "").split(";") if x.strip()]


# --------------------------------------------------------------------------
# Literals
# --------------------------------------------------------------------------

LIT_RE = re.compile(r'^"((?:[^"\\]|\\.)*)"(?:\^\^(\S+)|@([A-Za-z][A-Za-z0-9-]*))?$')


def parse_literal(text, reg, datatype=None):
    text = text.strip()
    m = LIT_RE.match(text)
    if m:
        value = m.group(1).replace('\\"', '"').replace("\\\\", "\\")
        if m.group(2):
            return Literal(value, datatype=reg.uri(m.group(2), "datatype"))
        if m.group(3):
            return Literal(value, lang=m.group(3))
        return Literal(value, datatype=datatype) if datatype else Literal(value)
    if datatype is not None and datatype != RDFS.Literal:
        return Literal(text, datatype=datatype)
    if re.fullmatch(r"[+-]?\d+", text):
        return Literal(text, datatype=XSD.integer)
    if re.fullmatch(r"[+-]?\d*\.\d+", text):
        return Literal(text, datatype=XSD.decimal)
    if text in ("true", "false"):
        return Literal(text, datatype=XSD.boolean)
    return Literal(text)


def literal_text(lit):
    """How a literal is written in a CSV cell (inverse of parse_literal)."""
    if lit.language:
        return f'"{lit}"@{lit.language}'
    guessed = parse_literal(str(lit), None) if not str(lit).startswith('"') else None
    if guessed is not None and guessed.datatype == lit.datatype and not lit.language:
        return str(lit)
    if lit.datatype is None and guessed is not None and guessed.datatype is None:
        return str(lit)
    escaped = str(lit).replace("\\", "\\\\").replace('"', '\\"')
    if lit.datatype is None:
        return f'"{escaped}"'
    return f'"{escaped}"^^{qname(lit.datatype)}'


def qname(u):
    for p, ns in PREFIXES.items():
        if str(u).startswith(str(ns)):
            return f"{p}:{str(u)[len(str(ns)):]}"
    return f"<{u}>"


# --------------------------------------------------------------------------
# Class expressions (Manchester syntax, as typed in Protégé)
# --------------------------------------------------------------------------

TOKEN_RE = re.compile(
    r'\s*(?:(?P<p>[(){},])'
    r'|(?P<lit>"(?:[^"\\]|\\.)*"(?:\^\^[^\s(){},]+|@[A-Za-z][A-Za-z0-9-]*)?)'
    r'|(?P<w>[^\s(){},]+))'
)


def tokenize(text):
    tokens, pos = [], 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            if text[pos:].strip():
                raise KBError(f"cannot read '{text[pos:]}'")
            break
        tok = m.group("p") or m.group("lit") or m.group("w")
        if tok:
            tokens.append(tok)
        pos = m.end()
    return tokens


class ExprBuilder:
    """Parses a Manchester-syntax class expression and writes it into the graph."""

    def __init__(self, g, reg):
        self.g, self.reg = g, reg

    def parse(self, text):
        self.toks, self.i, self.text = tokenize(text), 0, text
        if not self.toks:
            raise KBError("empty expression")
        node = self.or_()
        if self.i != len(self.toks):
            raise KBError(f"unexpected '{self.toks[self.i]}' in '{text}'")
        return node

    # token helpers
    def peek(self, k=0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def low(self, k=0):
        t = self.peek(k)
        return t.lower() if t else None

    def take(self):
        t = self.peek()
        if t is None:
            raise KBError(f"expression ends too early: '{self.text}'")
        self.i += 1
        return t

    def expect(self, t):
        got = self.take()
        if got != t:
            raise KBError(f"expected '{t}' but found '{got}' in '{self.text}'")

    # grammar
    def or_(self):
        parts = [self.and_()]
        while self.low() == "or":
            self.take()
            parts.append(self.and_())
        return parts[0] if len(parts) == 1 else self.boolean(OWL.unionOf, parts)

    def and_(self):
        parts = [self.unary()]
        while self.low() in ("and", "that"):
            self.take()
            parts.append(self.unary())
        return parts[0] if len(parts) == 1 else self.boolean(OWL.intersectionOf, parts)

    def unary(self):
        if self.low() == "not":
            self.take()
            inner = self.unary()
            b = BNode()
            self.g.add((b, RDF.type, OWL.Class))
            self.g.add((b, OWL.complementOf, inner))
            return b
        return self.primary()

    def primary(self):
        t = self.peek()
        if t is None:
            raise KBError(f"expression ends too early: '{self.text}'")
        if t == "(":
            self.take()
            e = self.or_()
            self.expect(")")
            return e
        if t == "{":
            self.take()
            members = [self.reg.uri(self.take(), "individual")]
            while self.peek() == ",":
                self.take()
                members.append(self.reg.uri(self.take(), "individual"))
            self.expect("}")
            b = BNode()
            self.g.add((b, RDF.type, OWL.Class))
            self.g.add((b, OWL.oneOf, self.collection(members)))
            return b
        if t.lower() == "inverse":
            self.take()
            p, kind = self.reg.prop(self.take())
            if kind != "object":
                raise KBError("'inverse' only works with object properties")
            inv = BNode()
            self.g.add((inv, OWL.inverseOf, p))
            return self.restriction(inv, "object")
        if self.low(1) in RESTRICTION_KW:
            p, kind = self.reg.prop(self.take())
            if kind == "annotation":
                raise KBError(f"annotation property '{t}' cannot be used in a class expression")
            return self.restriction(p, kind)
        return self.reg.uri(self.take(), "class")

    def filler(self, kind):
        if kind == "data":
            return self.reg.uri(self.take(), "datatype")
        return self.unary()

    def has_filler(self):
        t = self.peek()
        return t is not None and t not in (")", "}", ",") and t.lower() not in ("and", "or", "that")

    def restriction(self, p, kind):
        kw = self.take().lower()
        b = BNode()
        g = self.g
        g.add((b, RDF.type, OWL.Restriction))
        g.add((b, OWL.onProperty, p))
        if kw == "some":
            g.add((b, OWL.someValuesFrom, self.filler(kind)))
        elif kw == "only":
            g.add((b, OWL.allValuesFrom, self.filler(kind)))
        elif kw == "value":
            if kind == "data":
                tok = self.take()
                g.add((b, OWL.hasValue, parse_literal(tok, self.reg)))
            else:
                g.add((b, OWL.hasValue, self.reg.uri(self.take(), "individual")))
        elif kw == "self":
            g.add((b, OWL.hasSelf, Literal(True)))
        else:
            n = self.take()
            if not n.isdigit():
                raise KBError(f"'{kw}' needs a number, found '{n}'")
            num = Literal(int(n), datatype=XSD.nonNegativeInteger)
            if self.has_filler():
                f = self.filler(kind)
                pred = {"min": OWL.minQualifiedCardinality, "max": OWL.maxQualifiedCardinality,
                        "exactly": OWL.qualifiedCardinality}[kw]
                g.add((b, pred, num))
                g.add((b, OWL.onDataRange if kind == "data" else OWL.onClass, f))
            else:
                pred = {"min": OWL.minCardinality, "max": OWL.maxCardinality,
                        "exactly": OWL.cardinality}[kw]
                g.add((b, pred, num))
        return b

    def boolean(self, pred, parts):
        b = BNode()
        self.g.add((b, RDF.type, OWL.Class))
        self.g.add((b, pred, self.collection(parts)))
        return b

    def collection(self, items):
        head = BNode()
        Collection(self.g, head, list(items))
        return head


# --------------------------------------------------------------------------
# Reading CSV files
# --------------------------------------------------------------------------

def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        first = sample.splitlines()[0] if sample else ""
        if ";" in first and "," not in first:
            raise KBError(f"{path.name}: columns are separated by ';'. Save the file with ',' between "
                          "columns (Google Sheets: File > Download > CSV).")
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return [], []
        headers = [h.strip() for h in reader.fieldnames]
        rows = []
        for lineno, raw in enumerate(reader, start=2):
            row = {h.strip(): (v or "").strip() for h, v in raw.items() if h is not None}
            if None in raw and any((x or "").strip() for x in raw[None]):
                raise KBError(f"{path.name} line {lineno}: more cells than columns "
                              "(a cell with a comma must be in quotes)")
            if not any(row.values()) or row.get("name", "").startswith("#"):
                continue
            rows.append((lineno, row))
        return headers, rows


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

class Builder:
    def __init__(self, data_dir, base=None, iri=None):
        self.data_dir = Path(data_dir)
        self.g = Graph()
        self.errors = []
        self.warnings = []
        self.values = defaultdict(list)    # (individual, property name) -> values, from all files
        self.to_close = []                 # (individual, property name, where)
        if base:
            self.g.parse(base)
        found = next((s for s in self.g.subjects(RDF.type, OWL.Ontology)), None)
        self.iri = iri or (str(found) if found else DEFAULT_IRI)
        if not found:
            self.g.add((URIRef(self.iri), RDF.type, OWL.Ontology))
        sep = "" if self.iri.endswith(("#", "/")) else "#"
        self.ns = Namespace(self.iri + sep)
        self.g.bind("", self.ns)
        for p, n in PREFIXES.items():
            self.g.bind(p, n)
        self.reg = Registry(self.ns)
        self.reg.load_graph(self.g)
        self.expr = ExprBuilder(self.g, self.reg)

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def cell(self, where, col, fn):
        try:
            return fn()
        except KBError as e:
            self.err(f"{where}, column '{col}'", e)

    def run(self):
        if not self.data_dir.is_dir():
            raise KBError(f"folder not found: {self.data_dir}")
        files = sorted(self.data_dir.glob("*.csv"))
        if not files:
            raise KBError(f"no .csv files in {self.data_dir}")
        tables = {}
        for f in files:
            try:
                tables[f.name] = read_csv(f)
            except KBError as e:
                self.errors.append(str(e))
        ind_files = [n for n in tables if n not in SPECIAL_FILES]
        self.add_default_properties(tables)

        # 1. declare every name, so rows can refer to names defined later
        for fname, kind_of in [("classes.csv", lambda r: "class"),
                               ("properties.csv", lambda r: (r.get("kind") or "object").lower())]:
            for lineno, row in tables.get(fname, ([], []))[1]:
                where = f"{fname} line {lineno}"
                name = clean(row.get("name", ""))
                kind = kind_of(row)
                if not name:
                    self.err(where, "the 'name' cell is empty")
                elif kind not in KIND_TYPES or kind in ("class", "individual") and fname == "properties.csv":
                    self.err(where, f"kind must be object, data or annotation, not '{kind}'")
                else:
                    self.cell(where, "name", lambda: self.reg.declare(name, kind, where))
        entity_files = [n for n in ind_files if "name" in tables[n][0]]
        relation_files = [n for n in ind_files if "name" not in tables[n][0]]
        for fname in entity_files:
            headers, rows = tables[fname]
            for lineno, row in rows:
                where = f"{fname} line {lineno}"
                name = clean(row["name"])
                if name:
                    self.cell(where, "name", lambda: self.reg.declare(name, "individual", where))
                else:
                    self.err(where, "the 'name' cell is empty")
        for lineno, row in tables.get("properties.csv", ([], []))[1]:
            if (row.get("kind") or "").lower() == "data" and row.get("range"):
                r = split_list(row["range"])
                if len(r) == 1:
                    try:
                        self.reg.data_ranges[clean(row["name"])] = self.reg.uri(r[0], "datatype")
                    except KBError:
                        pass

        # 2. write the axioms
        if "classes.csv" in tables:
            self.classes(*tables["classes.csv"])
        if "properties.csv" in tables:
            self.properties(*tables["properties.csv"])
        for fname in entity_files:
            self.individuals(fname, *tables[fname])
        for fname in relation_files:
            self.relations(fname, *tables[fname])
        self.write_closures()
        if "axioms.csv" in tables:
            self.axioms(*tables["axioms.csv"])
        return self.g

    def add_default_properties(self, tables):
        headers, rows = tables.get("properties.csv", ([], []))
        in_csv = {clean(r.get("name", "")) for _, r in rows}
        added = []
        for d in DEFAULT_PROPERTIES:
            if d["name"] in in_csv or self.reg.kinds.get(d["name"]):
                continue
            rows = rows + [(f"default {d['name']}", dict(d))]
            added.append(d["name"])
        if added:
            cols = ["name", "kind", "domain", "range", "chain"]
            tables["properties.csv"] = (list(dict.fromkeys((headers or []) + cols)), rows)
            self.warnings.append("added properties that are not in the ontology yet (defined in build_kb.py, "
                                 "DEFAULT_PROPERTIES): " + ", ".join(added))

    def check_columns(self, fname, headers, allowed):
        for h in headers:
            if h and h not in allowed:
                self.err(fname, f"unknown column '{h}' (allowed: {', '.join(sorted(allowed))})")

    def annotate(self, s, row):
        if row.get("label"):
            self.g.add((s, RDFS.label, Literal(row["label"])))
        if row.get("comment"):
            self.g.add((s, RDFS.comment, Literal(row["comment"])))

    def classes(self, headers, rows):
        self.check_columns("classes.csv", headers,
                           {"name", "subclass_of", "equivalent_to", "disjoint_with", "label", "comment"})
        for lineno, row in rows:
            where = f"classes.csv line {lineno}"
            c = self.ns[clean(row["name"])]
            self.g.add((c, RDF.type, OWL.Class))
            for col, pred in [("subclass_of", RDFS.subClassOf), ("equivalent_to", OWL.equivalentClass),
                              ("disjoint_with", OWL.disjointWith)]:
                for e in split_list(row.get(col)):
                    node = self.cell(where, col, lambda: self.expr.parse(e))
                    if node is not None:
                        self.g.add((c, pred, node))
            self.annotate(c, row)

    def properties(self, headers, rows):
        self.check_columns("properties.csv", headers,
                           {"name", "kind", "subproperty_of", "domain", "range", "inverse_of",
                            "characteristics", "chain", "equivalent_to", "disjoint_with", "label", "comment"})
        for lineno, row in rows:
            where = f"properties.csv line {lineno}"
            name = clean(row.get("name", ""))
            kind = (row.get("kind") or "object").lower()
            if kind not in ("object", "data", "annotation"):
                continue
            p = self.ns[name]
            g = self.g
            g.add((p, RDF.type, KIND_TYPES[kind]))
            for parent in split_list(row.get("subproperty_of")):
                u = self.cell(where, "subproperty_of", lambda: self.reg.prop(parent)[0])
                if u is not None:
                    g.add((p, RDFS.subPropertyOf, u))
            for e in split_list(row.get("domain")):
                node = self.cell(where, "domain", lambda: self.expr.parse(e))
                if node is not None:
                    g.add((p, RDFS.domain, node))
            for e in split_list(row.get("range")):
                if kind == "object":
                    node = self.cell(where, "range", lambda: self.expr.parse(e))
                else:
                    node = self.cell(where, "range", lambda: self.reg.uri(e, "datatype")
                                     if ":" in e else self.reg.uri(e, "class"))
                if node is not None:
                    g.add((p, RDFS.range, node))
            for inv in split_list(row.get("inverse_of")):
                u = self.cell(where, "inverse_of", lambda: self.reg.uri(inv, "object"))
                if u is not None:
                    g.add((p, OWL.inverseOf, u))
            for ch in split_list(row.get("characteristics")):
                key = ch.lower().replace("-", "_").replace(" ", "_")
                if key not in CHARACTERISTICS:
                    self.err(f"{where}, column 'characteristics'",
                             f"unknown '{ch}' (allowed: {', '.join(CHARACTERISTICS)})")
                elif kind == "data" and key not in ("functional",):
                    self.err(f"{where}, column 'characteristics'", "data properties can only be functional")
                else:
                    g.add((p, RDF.type, CHARACTERISTICS[key]))
            for ch in split_list(row.get("chain")):
                parts = [x for x in re.split(r"\s+o\s+", ch.strip()) if x]
                if len(parts) < 2:
                    self.err(f"{where}, column 'chain'", f"write a chain as 'p1 o p2', not '{ch}'")
                    continue
                uris = [self.cell(where, "chain", lambda x=x: self.reg.uri(x, "object")) for x in parts]
                if None not in uris:
                    head = BNode()
                    Collection(g, head, uris)
                    g.add((p, OWL.propertyChainAxiom, head))
            for col, pred in [("equivalent_to", OWL.equivalentProperty),
                              ("disjoint_with", OWL.propertyDisjointWith)]:
                for other in split_list(row.get(col)):
                    u = self.cell(where, col, lambda: self.reg.prop(other)[0])
                    if u is not None:
                        g.add((p, pred, u))
            self.annotate(p, row)

    def property_columns(self, fname, headers, rows, reserved):
        """Map each column header that is a property to (uri, kind, negative?, name)."""
        cols = {}
        for h in headers:
            if not h or h in reserved:
                continue
            neg = h.lower().startswith("not ")
            pname = h[4:].strip() if neg else h
            try:
                p, kind = self.reg.prop(pname)
                cols[h] = (p, kind, neg, clean(pname))
            except KBError as e:
                if not any(row.get(h) for _, row in rows):
                    self.warnings.append(f"{fname}: column '{h}' is not a property yet and is empty, "
                                         "so it is skipped. Add it to properties.csv before filling it.")
                else:
                    self.err(f"{fname}, column '{h}'", "a column must be category, name, types, close, "
                             f"label, comment or a property. {e}")
        return cols

    def assert_values(self, i, row, cols, where):
        g = self.g
        for h, (p, kind, neg, pname) in cols.items():
            for v in split_list(row.get(h)):
                if kind == "object":
                    o = self.cell(where, h, lambda: self.reg.uri(v, "individual"))
                else:
                    o = self.cell(where, h, lambda: parse_literal(v, self.reg, self.reg.data_ranges.get(pname)))
                if o is None:
                    continue
                if neg:
                    b = BNode()
                    g.add((b, RDF.type, OWL.NegativePropertyAssertion))
                    g.add((b, OWL.sourceIndividual, i))
                    g.add((b, OWL.assertionProperty, p))
                    g.add((b, OWL.targetIndividual if kind == "object" else OWL.targetValue, o))
                else:
                    g.add((i, p, o))
                    if o not in self.values[(i, pname)]:
                        self.values[(i, pname)].append(o)

    def individuals(self, fname, headers, rows):
        cols = self.property_columns(fname, headers, rows, INDIVIDUAL_RESERVED)
        for lineno, row in rows:
            where = f"{fname} line {lineno}"
            i = self.ns[clean(row["name"])]
            g = self.g
            g.add((i, RDF.type, OWL.NamedIndividual))
            for e in split_list(row.get("types")):
                node = self.cell(where, "types", lambda: self.expr.parse(e))
                if node is not None:
                    g.add((i, RDF.type, node))
            self.assert_values(i, row, cols, where)
            for pname in split_list(row.get("close")):
                self.to_close.append((i, clean(pname), where))
            self.annotate(i, row)

    def relations(self, fname, headers, rows):
        """A file without a 'name' column: the first column names the individual (any header,
        e.g. 'cocktail'), the other columns are properties, e.g. a recipes file
        cocktail,hasIngredient / negroni,gin. An individual can have many rows."""
        subject_col = headers[0]
        cols = self.property_columns(fname, headers[1:], rows, {"category", "comment"})
        if len(headers) < 2:
            self.err(fname, "has no 'name' column. An individuals file needs 'name'; a relations file "
                     "needs a first column (who) plus property columns (e.g. cocktail,hasIngredient).")
            return
        for lineno, row in rows:
            where = f"{fname} line {lineno}"
            subj = row.get(subject_col, "")
            if not subj:
                self.err(where, f"the '{subject_col}' cell is empty")
                continue
            i = self.cell(where, subject_col, lambda: self.reg.uri(subj, "individual"))
            if i is not None:
                self.assert_values(i, row, cols, where)

    def write_closures(self):
        g = self.g
        for i, pname, where in self.to_close:
            try:
                p, kind = self.reg.prop(pname)
            except KBError as e:
                self.err(f"{where}, column 'close'", e)
                continue
            if kind != "object":
                self.err(f"{where}, column 'close'", f"'{pname}' is not an object property")
                continue
            vals = self.values.get((i, pname), [])
            if not vals:
                self.warnings.append(f"{where}: '{str(i).split('#')[-1]}' is closed on '{pname}' but has no "
                                     f"{pname} values in any file, so it is closed as having none.")
            r = BNode()
            g.add((i, RDF.type, r))
            g.add((r, RDF.type, OWL.Restriction))
            g.add((r, OWL.onProperty, p))
            if vals:
                one = BNode()
                g.add((one, RDF.type, OWL.Class))
                head = BNode()
                Collection(g, head, vals)
                g.add((one, OWL.oneOf, head))
                g.add((r, OWL.allValuesFrom, one))
            else:
                g.add((r, OWL.allValuesFrom, OWL.Nothing))

    def axioms(self, headers, rows):
        self.check_columns("axioms.csv", headers, {"kind", "members", "comment"})
        for lineno, row in rows:
            where = f"axioms.csv line {lineno}"
            kind = (row.get("kind") or "").strip().lower().replace("_", "")
            members = split_list(row.get("members"))
            g = self.g
            try:
                if kind in ("alldifferent", "differentindividuals"):
                    inds = [self.reg.uri(m, "individual") for m in members]
                    self.need(inds, 2)
                    b = BNode()
                    g.add((b, RDF.type, OWL.AllDifferent))
                    head = BNode()
                    Collection(g, head, inds)
                    g.add((b, OWL.distinctMembers, head))  # the form Protégé writes
                elif kind in ("sameindividual", "sameas"):
                    inds = [self.reg.uri(m, "individual") for m in members]
                    self.need(inds, 2)
                    for other in inds[1:]:
                        g.add((inds[0], OWL.sameAs, other))
                elif kind in ("alldisjointclasses", "disjointclasses"):
                    cls = [self.expr.parse(m) for m in members]
                    self.need(cls, 2)
                    if len(cls) == 2:
                        g.add((cls[0], OWL.disjointWith, cls[1]))
                    else:
                        b = BNode()
                        g.add((b, RDF.type, OWL.AllDisjointClasses))
                        head = BNode()
                        Collection(g, head, cls)
                        g.add((b, OWL.members, head))
                elif kind == "equivalentclasses":
                    cls = [self.expr.parse(m) for m in members]
                    self.need(cls, 2)
                    for other in cls[1:]:
                        g.add((cls[0], OWL.equivalentClass, other))
                elif kind == "subclassof":
                    if len(members) != 2:
                        raise KBError("SubClassOf needs exactly 2 members: sub;super")
                    g.add((self.expr.parse(members[0]), RDFS.subClassOf, self.expr.parse(members[1])))
                elif kind == "disjointunion":
                    if len(members) < 3:
                        raise KBError("DisjointUnion needs the class, then at least 2 parts")
                    c = self.reg.uri(members[0], "class")
                    parts = [self.expr.parse(m) for m in members[1:]]
                    head = BNode()
                    Collection(g, head, parts)
                    g.add((c, OWL.disjointUnionOf, head))
                elif kind in ("alldisjointproperties", "disjointproperties"):
                    ps = [self.reg.prop(m)[0] for m in members]
                    self.need(ps, 2)
                    if len(ps) == 2:
                        g.add((ps[0], OWL.propertyDisjointWith, ps[1]))
                    else:
                        b = BNode()
                        g.add((b, RDF.type, OWL.AllDisjointProperties))
                        head = BNode()
                        Collection(g, head, ps)
                        g.add((b, OWL.members, head))
                elif kind == "equivalentproperties":
                    ps = [self.reg.prop(m)[0] for m in members]
                    self.need(ps, 2)
                    for other in ps[1:]:
                        g.add((ps[0], OWL.equivalentProperty, other))
                else:
                    raise KBError(f"unknown kind '{row.get('kind')}'. Allowed: AllDifferent, SameIndividual, "
                                  "AllDisjointClasses, EquivalentClasses, SubClassOf, DisjointUnion, "
                                  "AllDisjointProperties, EquivalentProperties")
            except KBError as e:
                self.err(where, e)

    @staticmethod
    def need(items, n):
        if len(items) < n:
            raise KBError(f"needs at least {n} members")


def write_ttl(g, out):
    text = g.serialize(format="turtle")
    header = ("# GENERATED by build_kb.py from the CSV files in data/.\n"
              "# Do not edit this file by hand or save it from Protégé: change the CSVs and rebuild.\n\n")
    Path(out).write_text(header + text, encoding="utf-8")


# --------------------------------------------------------------------------
# Statistics for the grading checklist
# --------------------------------------------------------------------------

def report(g):
    ns = next((str(s) for s in g.subjects(RDF.type, OWL.Ontology)), "")
    def ours(t):
        return sorted({s for s in g.subjects(RDF.type, t) if isinstance(s, URIRef) and str(s).startswith(ns)})
    classes, objs, datas = ours(OWL.Class), ours(OWL.ObjectProperty), ours(OWL.DatatypeProperty)
    inds = ours(OWL.NamedIndividual)
    defined = [c for c in classes if any(True for _ in g.objects(c, OWL.equivalentClass))]
    preds = set(g.predicates())
    types = set(g.objects(None, RDF.type))
    beyond = []
    if OWL.oneOf in preds or OWL.hasValue in preds:
        beyond.append("O  nominals (oneOf {..} / value)")
    if preds & {OWL.minQualifiedCardinality, OWL.maxQualifiedCardinality, OWL.qualifiedCardinality}:
        beyond.append("Q  qualified number restrictions (min/max/exactly n C)")
    if preds & {OWL.minCardinality, OWL.maxCardinality, OWL.cardinality}:
        beyond.append("N  unqualified number restrictions")
    if OWL.inverseOf in preds:
        beyond.append("I  inverse properties")
    if any(o not in (OWL.topObjectProperty, OWL.topDataProperty) for o in g.objects(None, RDFS.subPropertyOf)):
        beyond.append("H  property hierarchy (subproperty_of)")
    if OWL.propertyChainAxiom in preds:
        beyond.append("R  property chains")
    if OWL.hasSelf in preds:
        beyond.append("R  self restriction")
    if types & {OWL.ReflexiveProperty, OWL.IrreflexiveProperty, OWL.AsymmetricProperty} or \
            OWL.propertyDisjointWith in preds or OWL.AllDisjointProperties in types:
        beyond.append("R  reflexive/irreflexive/asymmetric/disjoint properties")
    if OWL.TransitiveProperty in types:
        beyond.append("S  transitive properties")
    if types & {OWL.FunctionalProperty, OWL.InverseFunctionalProperty}:
        beyond.append("F  functional properties")
    if datas:
        beyond.append("D  data properties / datatypes")
    print(f"  classes: {len(classes)}   object properties: {len(objs)}   data properties: {len(datas)}   "
          f"individuals: {len(inds)}")
    print(f"  names in total: {len(classes) + len(objs) + len(datas) + len(inds)}   (full points: at least 50)")
    print(f"  defined classes (equivalent_to): {len(defined)}   (full points: at least 10)")
    if defined:
        print("    " + ", ".join(str(c)[len(ns) + 1:] if str(c).startswith(ns) else str(c) for c in defined))
    print(f"  constructs beyond ALC: {len({b[0] for b in beyond})} kinds   (full points: at least 5)")
    for b in beyond:
        print(f"    {b}")


# --------------------------------------------------------------------------
# Reasoning (HermiT through owlready2; needs Java)
# --------------------------------------------------------------------------

def reason(g, queries):
    try:
        from owlready2 import World, sync_reasoner, OwlReadyInconsistentOntologyError
    except ImportError:
        print("  (skipped: install owlready2 with 'pip install owlready2' to run the reasoner)")
        return True
    ns = next((str(s) for s in g.subjects(RDF.type, OWL.Ontology)), DEFAULT_IRI)
    ns = ns if ns.endswith(("#", "/")) else ns + "#"
    with tempfile.NamedTemporaryFile("w", suffix=".nt", delete=False) as f:
        f.write(g.serialize(format="nt"))
        path = f.name
    try:
        w = World()
        w.get_ontology("file://" + path).load()
        t = time.time()
        try:
            sync_reasoner(w, infer_property_values=True, debug=0)
        except Exception as e:
            if not isinstance(e, OwlReadyInconsistentOntologyError):
                if "Java" in str(e) or "java" in str(e):
                    print("  (skipped: the reasoner needs Java. Install it with 'brew install openjdk' and run\n"
                          "   export PATH=\"$(brew --prefix openjdk)/bin:$PATH\"  - or run the reasoner in Protégé)")
                    return True
                raise
            print("  INCONSISTENT: the reasoner found a contradiction.")
            print("  Open the file in Protégé and use Reasoner > Explain inconsistency to see why.")
            return False
        print(f"  consistent. HermiT took {time.time() - t:.1f} s (includes start-up of Java)")
        unsat = [c for c in w.inconsistent_classes() if c.iri != str(OWL.Nothing)]
        if unsat:
            print("  UNSATISFIABLE classes (can never have members): " + ", ".join(c.name for c in unsat))
        else:
            print("  coherent: no unsatisfiable classes")
        for q in queries:
            c = w[ns + clean(q)]
            if c is None:
                print(f"  {q}: no such class")
                continue
            names = sorted(i.name for i in c.instances())
            print(f"  {q} ({len(names)}): {', '.join(names) if names else '-'}")
        return not unsat
    finally:
        os.unlink(path)


# --------------------------------------------------------------------------
# Export: existing ontology -> CSV files
# --------------------------------------------------------------------------

class Renderer:
    """Writes class expressions from the graph in Manchester syntax."""

    def __init__(self, g, ns):
        self.g, self.ns = g, ns

    def name(self, u):
        if isinstance(u, Literal):
            return literal_text(u)
        if isinstance(u, URIRef):
            if str(u).startswith(self.ns):
                return str(u)[len(self.ns):]
            return qname(u)
        raise KBError(f"cannot write blank node {u} as a name")

    def items(self, head):
        return list(Collection(self.g, head))

    def prop(self, p):
        if isinstance(p, BNode):
            inv = self.g.value(p, OWL.inverseOf)
            if inv is None:
                raise KBError("unsupported property expression")
            return f"inverse {self.name(inv)}"
        return self.name(p)

    def expr(self, n, nested=False):
        g = self.g
        if isinstance(n, URIRef):
            return self.name(n)
        wrap = (lambda s: f"({s})") if nested else (lambda s: s)
        if (lst := g.value(n, OWL.intersectionOf)) is not None:
            return wrap(" and ".join(self.expr(x, True) for x in self.items(lst)))
        if (lst := g.value(n, OWL.unionOf)) is not None:
            return wrap(" or ".join(self.expr(x, True) for x in self.items(lst)))
        if (x := g.value(n, OWL.complementOf)) is not None:
            return "not " + self.expr(x, True)
        if (lst := g.value(n, OWL.oneOf)) is not None:
            return "{" + ", ".join(self.name(x) for x in self.items(lst)) + "}"
        p = g.value(n, OWL.onProperty)
        if p is not None:
            ps = self.prop(p)
            if (x := g.value(n, OWL.someValuesFrom)) is not None:
                return wrap(f"{ps} some {self.expr(x, True)}")
            if (x := g.value(n, OWL.allValuesFrom)) is not None:
                return wrap(f"{ps} only {self.expr(x, True)}")
            if (x := g.value(n, OWL.hasValue)) is not None:
                return wrap(f"{ps} value {self.name(x)}")
            if g.value(n, OWL.hasSelf) is not None:
                return wrap(f"{ps} Self")
            for pred, kw in [(OWL.minQualifiedCardinality, "min"), (OWL.maxQualifiedCardinality, "max"),
                             (OWL.qualifiedCardinality, "exactly")]:
                if (x := g.value(n, pred)) is not None:
                    f = g.value(n, OWL.onClass) or g.value(n, OWL.onDataRange)
                    return wrap(f"{ps} {kw} {x} {self.expr(f, True)}")
            for pred, kw in [(OWL.minCardinality, "min"), (OWL.maxCardinality, "max"),
                             (OWL.cardinality, "exactly")]:
                if (x := g.value(n, pred)) is not None:
                    return wrap(f"{ps} {kw} {x}")
        raise KBError(f"unsupported class expression: {list(g.predicate_objects(n))}")


def export(ttl, out_dir, split):
    g = Graph().parse(ttl)
    onto = next((s for s in g.subjects(RDF.type, OWL.Ontology)), None)
    iri = str(onto) if onto else DEFAULT_IRI
    ns = iri if iri.endswith(("#", "/")) else iri + "#"
    R = Renderer(g, ns)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    def ours(t):
        return sorted({s for s in g.subjects(RDF.type, t) if isinstance(s, URIRef) and str(s).startswith(ns)})

    def ann(s):
        return {"label": str(g.value(s, RDFS.label) or ""), "comment": str(g.value(s, RDFS.comment) or "")}

    def write(fname, headers, rows):
        with open(out / fname, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"  {fname}: {len(rows)} rows")

    def drop_empty(headers, rows, keep):
        return [h for h in headers if h in keep or any(r.get(h) for r in rows)]

    # classes
    rows = []
    for c in ours(OWL.Class):
        rows.append({"name": R.name(c),
                     "subclass_of": ";".join(R.expr(o) for o in g.objects(c, RDFS.subClassOf)),
                     "equivalent_to": ";".join(R.expr(o) for o in g.objects(c, OWL.equivalentClass)),
                     "disjoint_with": ";".join(R.expr(o) for o in g.objects(c, OWL.disjointWith)),
                     **ann(c)})
    headers = ["name", "subclass_of", "equivalent_to", "disjoint_with", "label", "comment"]
    write("classes.csv", drop_empty(headers, rows, {"name", "subclass_of", "equivalent_to"}), rows)

    # properties
    rows = []
    for kind, t in [("object", OWL.ObjectProperty), ("data", OWL.DatatypeProperty),
                    ("annotation", OWL.AnnotationProperty)]:
        for p in ours(t):
            chars = [k for k, ct in CHARACTERISTICS.items() if (p, RDF.type, ct) in g]
            chains = [" o ".join(R.name(x) for x in R.items(h)) for h in g.objects(p, OWL.propertyChainAxiom)]
            rows.append({"name": R.name(p), "kind": kind,
                         "subproperty_of": ";".join(R.name(o) for o in g.objects(p, RDFS.subPropertyOf)
                                                    if o not in (OWL.topObjectProperty, OWL.topDataProperty)),
                         "domain": ";".join(R.expr(o) for o in g.objects(p, RDFS.domain)),
                         "range": ";".join(R.expr(o) for o in g.objects(p, RDFS.range)),
                         "inverse_of": ";".join(R.name(o) for o in g.objects(p, OWL.inverseOf)),
                         "characteristics": ";".join(chars), "chain": ";".join(chains),
                         "equivalent_to": ";".join(R.name(o) for o in g.objects(p, OWL.equivalentProperty)),
                         "disjoint_with": ";".join(R.name(o) for o in g.objects(p, OWL.propertyDisjointWith)),
                         **ann(p)})
    headers = ["name", "kind", "subproperty_of", "domain", "range", "inverse_of", "characteristics",
               "chain", "equivalent_to", "disjoint_with", "label", "comment"]
    write("properties.csv", drop_empty(headers, rows, {"name", "kind", "domain", "range"}), rows)

    # individuals, split into files by type
    props = {p: k for k, t in [("object", OWL.ObjectProperty), ("data", OWL.DatatypeProperty),
                               ("annotation", OWL.AnnotationProperty)] for p in ours(t)}
    parents = defaultdict(set)
    for c in ours(OWL.Class):
        for o in g.objects(c, RDFS.subClassOf):
            if isinstance(o, URIRef):
                parents[c].add(o)

    def ancestors(c):
        seen, todo = set(), [c]
        while todo:
            x = todo.pop()
            if x not in seen:
                seen.add(x)
                todo.extend(parents[x])
        return seen

    def named_types(t):
        if isinstance(t, URIRef):
            return {t}
        lst = g.value(t, OWL.intersectionOf)
        return {x for x in R.items(lst) if isinstance(x, URIRef)} if lst is not None else set()

    negs = defaultdict(list)
    for b in g.subjects(RDF.type, OWL.NegativePropertyAssertion):
        src, p = g.value(b, OWL.sourceIndividual), g.value(b, OWL.assertionProperty)
        tgt = g.value(b, OWL.targetIndividual) or g.value(b, OWL.targetValue)
        negs[src].append((p, tgt))

    files = defaultdict(list)
    for i in ours(OWL.NamedIndividual):
        types = [t for t in g.objects(i, RDF.type) if t != OWL.NamedIndividual]
        vals = defaultdict(list)
        for p, o in g.predicate_objects(i):
            if p in props:
                vals[p].append(o)
        close, keep = [], []
        for t in types:
            p = g.value(t, OWL.onProperty) if isinstance(t, BNode) else None
            a = g.value(t, OWL.allValuesFrom) if p is not None else None
            lst = g.value(a, OWL.oneOf) if isinstance(a, BNode) else None
            n_preds = len(list(g.predicate_objects(t))) if p is not None else 0
            if lst is not None and n_preds == 3 and set(R.items(lst)) == set(vals.get(p, [])) \
                    and len(R.items(lst)) == len(set(R.items(lst))):
                close.append(R.name(p))
                vals[p] = R.items(lst)  # keep the order of the closure list
            elif a == OWL.Nothing and n_preds == 3 and not vals.get(p):
                close.append(R.name(p))
                vals.setdefault(p, [])
            else:
                keep.append(t)
        row = {"name": R.name(i), "types": ";".join(R.expr(t) for t in keep), "close": ";".join(close), **ann(i)}
        for p, objs in vals.items():
            row[R.name(p)] = ";".join(R.name(o) for o in objs)
        for p, tgt in negs.get(i, []):
            key = "not " + R.name(p)
            row[key] = ";".join(filter(None, [row.get(key), R.name(tgt)]))
        anc = set().union(*(ancestors(c) for t in types for c in named_types(t))) if types else set()
        target = next((f for cls, f in split if (URIRef(ns + cls) in anc)), "individuals")
        files[target].append(row)

    for fname, rows in sorted(files.items()):
        pcols = sorted({k for r in rows for k in r} - INDIVIDUAL_RESERVED,
                       key=lambda k: (k.startswith("not "), k))
        headers = ["name", "types", "close"] + pcols + ["label", "comment"]
        write(f"{fname}.csv", drop_empty(headers, rows, {"name", "types"}), rows)

    # general axioms
    rows = []
    for b in g.subjects(RDF.type, OWL.AllDifferent):
        lst = g.value(b, OWL.members) or g.value(b, OWL.distinctMembers)
        rows.append({"kind": "AllDifferent", "members": ";".join(R.name(x) for x in R.items(lst))})
    for b in g.subjects(RDF.type, OWL.AllDisjointClasses):
        rows.append({"kind": "AllDisjointClasses",
                     "members": ";".join(R.expr(x) for x in R.items(g.value(b, OWL.members)))})
    for b in g.subjects(RDF.type, OWL.AllDisjointProperties):
        rows.append({"kind": "AllDisjointProperties",
                     "members": ";".join(R.name(x) for x in R.items(g.value(b, OWL.members)))})
    for s, o in g.subject_objects(OWL.sameAs):
        rows.append({"kind": "SameIndividual", "members": f"{R.name(s)};{R.name(o)}"})
    for s, o in g.subject_objects(OWL.differentFrom):
        rows.append({"kind": "AllDifferent", "members": f"{R.name(s)};{R.name(o)}"})
    for c, lst in g.subject_objects(OWL.disjointUnionOf):
        rows.append({"kind": "DisjointUnion",
                     "members": ";".join([R.name(c)] + [R.expr(x) for x in R.items(lst)])})
    for s, o in g.subject_objects(RDFS.subClassOf):
        if isinstance(s, BNode):
            rows.append({"kind": "SubClassOf", "members": f"{R.expr(s)};{R.expr(o)}"})
    for s, o in g.subject_objects(OWL.equivalentClass):
        if isinstance(s, BNode):
            rows.append({"kind": "EquivalentClasses", "members": f"{R.expr(s)};{R.expr(o)}"})
    write("axioms.csv", ["kind", "members", "comment"], rows)
    return iri


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build the .ttl from the CSV files")
    b.add_argument("data", nargs="?", default=".", help="folder with the CSV files (default: this folder)")
    b.add_argument("-o", "--out", default=DEFAULT_OUT, help=f"file to write (default: {DEFAULT_OUT})")
    b.add_argument("--base", help=f"hand-made .ttl to start from, kept as it is (default: {DEFAULT_BASE} if it exists)")
    b.add_argument("--no-base", action="store_true", help="build only from the CSV files")
    b.add_argument("--iri", help=f"ontology IRI (default: from --base, else {DEFAULT_IRI})")
    b.add_argument("--reason", action="store_true", help="run HermiT after building (needs Java + owlready2)")
    b.add_argument("--query", default="", help="comma-separated classes to list instances of (implies --reason)")

    e = sub.add_parser("export", help="turn an existing .ttl into CSV files")
    e.add_argument("ttl")
    e.add_argument("-o", "--out", default="data")
    e.add_argument("--split", default="Drink=drinks,Flavour=flavours,Person=customers,Ingredient=ingredients",
                   help="which individuals go to which file: Class=file,... (first match wins)")
    e.add_argument("--no-verify", action="store_true", help="skip rebuilding to check nothing was lost")

    c = sub.add_parser("check", help="statistics and reasoner run for any .ttl")
    c.add_argument("ttl")
    c.add_argument("--query", default="")

    args = ap.parse_args()
    try:
        if args.cmd == "build":
            base = args.base
            if base is None and not args.no_base and Path(DEFAULT_BASE).exists():
                base = DEFAULT_BASE
            if base and Path(base).resolve() == Path(args.out).resolve():
                raise KBError(f"the output would overwrite the base file {base}. Choose another name with -o.")
            if base:
                print(f"Starting from {base} (not changed), adding the CSV files in '{args.data}'")
            builder = Builder(args.data, base, args.iri)
            g = builder.run()
            if builder.errors:
                print(f"Found {len(builder.errors)} problem(s). Nothing was written.\n")
                for msg in builder.errors:
                    print("  - " + msg)
                sys.exit(1)
            write_ttl(g, args.out)
            print(f"Wrote {args.out}")
            for msg in builder.warnings:
                print("  Note: " + msg)
            report(g)
            queries = [q for q in args.query.split(",") if q.strip()]
            if args.reason or queries:
                print("Reasoner:")
                if not reason(g, queries):
                    sys.exit(2)
        elif args.cmd == "export":
            split = [tuple(x.split("=", 1)) for x in args.split.split(",") if "=" in x]
            print(f"Exporting {args.ttl} to {args.out}/")
            iri = export(args.ttl, args.out, split)
            if not args.no_verify:
                from rdflib.compare import isomorphic, graph_diff, to_isomorphic
                original = Graph().parse(args.ttl)
                original.remove((None, RDFS.subPropertyOf, OWL.topObjectProperty))
                original.remove((None, RDFS.subPropertyOf, OWL.topDataProperty))
                builder = Builder(args.out, iri=iri)
                rebuilt = builder.run()
                if builder.errors:
                    print("WARNING: the exported CSVs do not build cleanly:")
                    for msg in builder.errors:
                        print("  - " + msg)
                elif isomorphic(original, rebuilt):
                    print("Verified: building from these CSVs gives exactly the same ontology.")
                else:
                    _, only_old, only_new = graph_diff(to_isomorphic(original), to_isomorphic(rebuilt))
                    print(f"WARNING: rebuilding differs from the original "
                          f"({len(only_old)} triples lost, {len(only_new)} added). Lost:")
                    for t in list(only_old)[:20]:
                        print("   ", t)
        elif args.cmd == "check":
            g = Graph().parse(args.ttl)
            report(g)
            print("Reasoner:")
            reason(g, [q for q in args.query.split(",") if q.strip()])
    except KBError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()