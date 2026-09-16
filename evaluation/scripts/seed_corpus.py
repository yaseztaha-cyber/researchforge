"""Seed a realistic vector corpus (500-2000 chunks) for PostgreSQL validation.

Uses openly licensed/public-domain style templated content per domain.
Records document_id, source, topic, chunk counts.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.session import SessionLocal, init_db
from app.models.db_models import Document, DocumentChunk
from app.services.documents.chunking import chunk_document_v3
from app.services.embeddings.factory import get_embedding_provider
from app.services.embeddings.cache import EmbeddingCache
from app.services.vector_store import get_vector_store
import hashlib, datetime as dt, json

TEMPLATES = {
    "environmental": "Environmental science studies show that {topic} affects ecosystems via {mechanism}. Field measurements from 2019-2023 indicate {finding}. Mitigation via {mitigation} reduces impact. Section: {section}.",
    "energy": "Energy systems analysis: {topic} requires {mechanism}. Grid data 2020-2024 shows {finding}. Deployment of {mitigation} improves efficiency. Section: {section}.",
    "biology": "Biology review: {topic} involves {mechanism}. Lab studies 2018-2023 report {finding}. Therapeutic {mitigation} shows promise. Section: {section}.",
    "computer science": "Computer science survey: {topic} uses {mechanism}. Benchmarks 2021-2024 demonstrate {finding}. Technique {mitigation} scales. Section: {section}.",
    "engineering": "Engineering report: {topic} exhibits {mechanism}. Tests 2019-2024 measure {finding}. Design {mitigation} enhances durability. Section: {section}.",
    "general science": "Science overview: {topic} relates to {mechanism}. Evidence 2020-2024 suggests {finding}. Approach {mitigation} advances understanding. Section: {section}.",
}

def make_chunk_text(domain, idx):
    import random
    # Deterministic per idx
    random.seed(hash(f"{domain}-{idx}") % 2**32)
    topics = ["desalination brine", "solar intermittency", "coral calcification", "transformer attention", "concrete fatigue", "aerosol forcing", "lithium degradation", "algal blooms", "mRNA immunity", "5G slicing"]
    mechs = ["salinity gradients", "photovoltaic variability", "aragonite saturation", "self-attention", "microcracking", "CCN activation", "capacity fade", "nutrient runoff", "antibody kinetics", "QoS isolation"]
    findings = ["15% increase within 100m", "20% capacity factor", "pH drop 0.1 reduces calcification 30%", "quadratic scaling", "corrosion doubles crack rate", "radiative forcing -0.5 W/m2", "cycle life 500-1000", "hypoxia threshold 2mg/L", "T-cell memory 6 months", "latency <10ms"]
    mits = ["diffuser systems", "storage", "marine protected areas", "sparse attention", "self-healing", "ensemble modeling", "thermal management", "buffer strips", "booster protocols", "network hardening"]
    sections = ["Introduction", "Methods", "Results", "Discussion", "Mitigation", "Conclusion"]
    return TEMPLATES[domain].format(topic=random.choice(topics), mechanism=random.choice(mechs), finding=random.choice(findings), mitigation=random.choice(mits), section=random.choice(sections)) + f" Chunk {idx} provides additional context on {domain} with reproducible measurements."

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=600)
    ap.add_argument("--domains", nargs="*", default=list(TEMPLATES.keys()))
    args = ap.parse_args()
    init_db()
    db = SessionLocal()
    emb = get_embedding_provider()
    cache = EmbeddingCache(emb)
    vs = get_vector_store()
    total = 0
    docs = []
    try:
        per_domain = max(1, args.chunks // max(1, len(args.domains)))
        for domain in args.domains:
            # Create one document per domain with many synthetic chunks
            chash = hashlib.sha256(f"{domain}-seed-v1-{per_domain}".encode()).hexdigest()
            existing = db.query(Document).filter(Document.content_hash==chash).first()
            if existing:
                print(f"Skipping existing {domain} {existing.id}")
                total += existing.num_chunks
                docs.append({"document_id": existing.id, "domain": domain, "chunks": existing.num_chunks, "embedding_model": existing.embedding_model, "embedding_dim": existing.embedding_dim})
                continue
            now = dt.datetime.now(dt.timezone.utc)
            doc = Document(filename=f"{domain}_corpus.pdf", content_hash=chash, num_chunks=per_domain, version=1, first_seen=now, last_seen=now, embedding_model=emb.name, embedding_dim=emb.dim)
            db.add(doc)
            db.flush()
            # Generate many chunks directly
            chunk_texts = [make_chunk_text(domain, i) for i in range(per_domain)]
            vecs = cache.embed_many_cached(chunk_texts)
            for i, (txt, vec) in enumerate(zip(chunk_texts, vecs)):
                ch = hashlib.sha256(txt.encode()).hexdigest()
                db.add(DocumentChunk(document_id=doc.id, chunk_index=i, page=(i//10)+1, section="Results", heading=f"Section {i%5}", text=txt, char_start=i*500, char_end=i*500+len(txt), content_hash=ch, embedding=vec, embedding_model=emb.name, embedding_dim=emb.dim))
            db.commit()
            vs.upsert(db, db.query(DocumentChunk).filter(DocumentChunk.document_id==doc.id).all())
            total += per_domain
            docs.append({"document_id": doc.id, "domain": domain, "chunks": per_domain, "embedding_model": emb.name, "embedding_dim": emb.dim})
            print(f"Seeded {domain}: {per_domain} chunks")
            if total >= args.chunks:
                break
        print(json.dumps({"total_chunks": total, "documents": docs, "vector_store": vs.__class__.__name__}, indent=2))
        out = Path(__file__).resolve().parents[2] / "evaluation" / "reports" / "seed_corpus.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"total_chunks": total, "documents": docs}, indent=2))
    finally:
        db.close()
