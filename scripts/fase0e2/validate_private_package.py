#!/usr/bin/env python3
# validate_private_package.py — Valida o pacote de origem da Fase 0E1
import os
import sys
import json
import hashlib
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Validação de Pacote Privado - Fase 0E2")
    parser.add_argument("--source", required=True, help="Diretório do pacote de origem da Fase 0E1")
    return parser.parse_args()

def check_security(path):
    # Rejeita symlinks
    if os.path.islink(path):
        print(f"ERRO: Symlink detectado em {path}", file=sys.stderr)
        sys.exit(2)
    # Rejeita path traversal e acessos fora dos caminhos permitidos (config ou tmp para testes)
    real_path = os.path.realpath(path)
    if not (real_path.startswith("/root/.config/wins_agro/") or real_path.startswith("/tmp/")):
        print(f"ERRO: Acesso fora do diretório permitido para {path}", file=sys.stderr)
        sys.exit(2)

def validate_permissions(path, is_dir=False):
    st = os.stat(path)
    mode = st.st_mode & 0o777
    expected = 0o700 if is_dir else 0o600
    if mode != expected:
        print(f"ERRO: Permissões inválidas para {path}. Esperado {oct(expected)}, obtido {oct(mode)}", file=sys.stderr)
        sys.exit(3)

def compute_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def main():
    args = parse_args()
    source_dir = os.path.abspath(args.source)

    # 1. Rejeita execuções superseded
    superseded = [
        "20260713_164030_production",
        "20260713_164036_production",
        "20260713_164049_production"
    ]
    for sup in superseded:
        if sup in source_dir:
            print(f"ERRO: Execução superseded detectada: {sup}", file=sys.stderr)
            sys.exit(4)

    # 2. Valida segurança e permissões do diretório raiz
    if not os.path.isdir(source_dir):
        print(f"ERRO: Diretório de origem não existe: {source_dir}", file=sys.stderr)
        sys.exit(1)

    check_security(source_dir)
    validate_permissions(source_dir, is_dir=True)

    # 3. Valida checksums
    checksum_file = os.path.join(source_dir, "checksums.sha256")
    if not os.path.exists(checksum_file):
        print(f"ERRO: Arquivo checksums.sha256 não encontrado", file=sys.stderr)
        sys.exit(1)

    check_security(checksum_file)
    validate_permissions(checksum_file, is_dir=False)

    expected_files = {
        "README_PRIVATE.txt",
        "checksums.sha256",
        "execution_manifest_private.json",
        "inventory_private.csv",
        "inventory_private.json",
        "inventory_sanitized.json",
        "mapping_conflicts_private.csv",
        "mapping_proposals_private.csv",
        "mapping_proposals_private.json",
        "mapping_review_checklist_private.csv",
        "salt.bin"
    }

    # Valida integridade física dos arquivos listados no checksum
    with open(checksum_file, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 2:
                continue
            h, fname = parts[0], parts[1]
            filepath = os.path.join(source_dir, fname)

            if fname not in expected_files:
                print(f"ERRO: Arquivo inesperado listado no checksum: {fname}", file=sys.stderr)
                sys.exit(1)

            if not os.path.exists(filepath):
                print(f"ERRO: Arquivo ausente: {fname}", file=sys.stderr)
                sys.exit(1)

            check_security(filepath)
            validate_permissions(filepath, is_dir=False)

            computed = compute_sha256(filepath)
            if computed != h:
                print(f"ERRO: Checksum divergente para {fname}. Esperado {h}, obtido {computed}", file=sys.stderr)
                sys.exit(1)

    # 4. Valida manifest
    manifest_path = os.path.join(source_dir, "execution_manifest_private.json")
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    if manifest.get("timestamp") != "20260713_165551":
        print(f"ERRO: Timestamp incorreto no manifesto: {manifest.get('timestamp')}", file=sys.stderr)
        sys.exit(1)

    # 5. Valida propostas estruturais
    proposals_path = os.path.join(source_dir, "mapping_proposals_private.json")
    with open(proposals_path, "r") as f:
        proposals = json.load(f)

    if len(proposals) != 5:
        print(f"ERRO: Quantidade incorreta de propostas: {len(proposals)}", file=sys.stderr)
        sys.exit(1)

    for idx, prop in enumerate(proposals):
        if prop.get("approved") is not False:
            print(f"ERRO: Proposta {idx} com aprovacao positiva (approved nao e False)", file=sys.stderr)
            sys.exit(1)
        if prop.get("confidence_class") != "F":
            print(f"ERRO: Proposta {idx} com classe diferente de F: {prop.get('confidence_class')}", file=sys.stderr)
            sys.exit(1)

    print("source_valid=true")
    sys.exit(0)

if __name__ == '__main__':
    main()
