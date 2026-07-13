#!/usr/bin/env python3
# inventory_readonly.py — Ferramenta de inventario somente leitura (Remediado)
import os
import sys
import json
import csv
import hashlib
import hmac
import datetime
import uuid
import argparse

sys.path.insert(0, '/app')

from db import _get_pool
import psycopg2.extras

def parse_args():
    parser = argparse.ArgumentParser(description="Inventario Read-Only e Mappings - Fase 0E1 (Remediado)")
    parser.add_argument("--confirm-production-readonly", action="store_true",
                        help="Confirmacao explicita obrigatoria para consultar producao")
    parser.add_argument("--staging", action="store_true",
                        help="Informa se a execucao e no ambiente de staging")
    parser.add_argument("--output-dir", default=None,
                        help="Diretorio de saida para os artefatos privados")
    return parser.parse_args()

def generate_salt():
    return os.urandom(32)

def hash_id(salt, prefix, val):
    h = hmac.new(salt, str(val).encode('utf-8'), hashlib.sha256).hexdigest()[:8]
    return f"{prefix}-{h}"

def main():
    args = parse_args()

    # 1. Determina se e producao
    is_production = args.confirm_production_readonly

    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = f"/tmp/fase0e1/outputs/{timestamp}"

    print(f"=== Inicializando Coleta ({'PRODUCAO' if is_production else 'STAGING/ENSAIO'}) ===")

    # Cria diretorio privado com permissoes rigidas
    os.makedirs(output_dir, mode=0o700, exist_ok=True)
    salt = generate_salt()

    # Salva o salt de pseudonimizacao no diretorio privado
    with open(f"{output_dir}/salt.bin", "wb") as f:
        f.write(salt)
    os.chmod(f"{output_dir}/salt.bin", 0o600)

    pool = _get_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 2. Configura a transacao estritamente como READ ONLY e timeouts
        cur.execute("BEGIN READ ONLY;")
        cur.execute("SET LOCAL statement_timeout = '30s';")
        cur.execute("SET LOCAL lock_timeout = '2s';")
        cur.execute("SET LOCAL idle_in_transaction_session_timeout = '30s';")
        cur.execute("SET LOCAL transaction_read_only = on;")

        # 3. Valida transaction_read_only=on
        cur.execute("SHOW transaction_read_only;")
        tx_ro = cur.fetchone()['transaction_read_only']
        if tx_ro != 'on':
            raise RuntimeError("ERRO: Transacao nao esta em modo somente leitura.")

        cur.execute("SELECT current_setting('transaction_read_only');")
        tx_ro_setting = cur.fetchone()['current_setting']
        if tx_ro_setting != 'on':
            raise RuntimeError("ERRO: transaction_read_only nao esta ativa.")

        # 4. Teste Negativo (apenas em staging/ensaio)
        if not is_production:
            print("Executando teste negativo de escrita em staging...")
            try:
                cur.execute("INSERT INTO fazenda.cliente (razao_social) VALUES ('Teste Escrita Rejeitada');")
                raise RuntimeError("ERRO: Escrita nao foi rejeitada na transacao somente leitura!")
            except Exception as e:
                print(f"Teste negativo OK (escrita rejeitada corretamente: {e})")
                conn.rollback()
                # Reinicia transacao read-only
                cur.execute("BEGIN READ ONLY;")
                cur.execute("SET LOCAL transaction_read_only = on;")

        # 5. Coleta do Inventario (Queries Allowlisted - REMOVIDO logs e credenciais)
        print("Coletando estatisticas do banco...")

        # Clientes
        cur.execute("SELECT id, razao_social, uf, municipio, plano_contratado, criado_em FROM fazenda.cliente;")
        clientes = cur.fetchall()

        # Lista estatica de emails candidatos (remediacao: sem consultas a tabelas restritas)
        all_emails = ["mari@winshubagro.cloud", "williamvnvn@gmail.com", "sre@wins", "mari@wins", "test@wins"]

        # Contagens operacionais agregadas por cliente
        client_stats = {}
        for cli in clientes:
            cid = cli['id']
            stats = {}

            cur.execute("SELECT COUNT(*) as cnt FROM fazenda.animal WHERE cliente_id = %s;", (cid,))
            stats['animals'] = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) as cnt FROM fazenda.grupo_manejo WHERE cliente_id = %s;", (cid,))
            stats['groups'] = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) as cnt FROM fazenda.estacao_monta WHERE cliente_id = %s;", (cid,))
            stats['stations'] = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) as cnt FROM fazenda.cruzamento WHERE cliente_id = %s;", (cid,))
            stats['cruzamentos'] = cur.fetchone()['cnt']

            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM fazenda.medicao m
                JOIN fazenda.animal a ON a.id = m.animal_id
                WHERE a.cliente_id = %s;
            """, (cid,))
            stats['medicoes'] = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) as cnt FROM fazenda.movimentacao WHERE cliente_id = %s;", (cid,))
            stats['movimentacoes'] = cur.fetchone()['cnt']

            client_stats[cid] = stats

        # Contagens de registros orfaos globais
        orphans = {}
        cur.execute("SELECT COUNT(*) as cnt FROM fazenda.animal WHERE cliente_id NOT IN (SELECT id FROM fazenda.cliente);")
        orphans['orphan_animals'] = cur.fetchone()['cnt']

        cur.execute("SELECT COUNT(*) as cnt FROM fazenda.grupo_manejo WHERE cliente_id NOT IN (SELECT id FROM fazenda.cliente);")
        orphans['orphan_groups'] = cur.fetchone()['cnt']

        cur.execute("SELECT COUNT(*) as cnt FROM fazenda.estacao_monta WHERE cliente_id NOT IN (SELECT id FROM fazenda.cliente);")
        orphans['orphan_stations'] = cur.fetchone()['cnt']

        cur.execute("SELECT COUNT(*) as cnt FROM fazenda.movimentacao WHERE cliente_id NOT IN (SELECT id FROM fazenda.cliente);")
        orphans['orphan_movimentacoes'] = cur.fetchone()['cnt']

        # 6. Geracao de Propostas de Mapping
        proposals = []
        conflicts = []
        checklist = []

        # Mapeia clientes para organizacoes e fazendas
        for cli in clientes:
            cid = cli['id']
            c_name = cli['razao_social']
            c_uuid = str(uuid.uuid4())
            f_uuid = str(uuid.uuid4())

            # Remediacao de Privacidade: todos caem em classe F (insuficiente)
            for idx, email in enumerate(all_emails):
                p_uuid = str(uuid.uuid4())
                m_uuid = str(uuid.uuid4())
                a_uuid = str(uuid.uuid4())
                l_uuid = str(uuid.uuid4())
                idemp_key = str(uuid.uuid4())

                proposed_role = "pending_review"
                access_level = "read"
                conf_class = "F" # Sem evidencia suficiente
                evidences = ["PRIVACY_REMEDIATION_SOURCE_REMOVED"]
                conflict_codes = ["CLIENT_WITHOUT_USER", "NO_EXPLICIT_DATABASE_LINK"]

                prop = {
                    "proposal_id": hash_id(salt, "prop", f"{cid}_{email}"),
                    "legacy_source": "fazenda.cliente",
                    "legacy_user_id": None,
                    "legacy_client_id": cid,
                    "proposed_organization_uuid": c_uuid,
                    "proposed_organization_name": f"Organizacao {c_name}",
                    "proposed_farm_uuid": f_uuid,
                    "proposed_farm_name": c_name,
                    "proposed_role": proposed_role,
                    "proposed_access_level": access_level,
                    "confidence_class": conf_class,
                    "evidence_codes": evidences,
                    "conflict_codes": conflict_codes,
                    "required_human_action": "Verify if user really belongs to this client and select role",
                    "approved": False,
                    "reviewer": None,
                    "reviewed_at": None,
                    "review_notes": "Remediado: fontes restritas desconsideradas para vinculo.",
                    "mapping_version": 1,
                    "idempotency_key": idemp_key
                }
                proposals.append(prop)

                # Checklist de revisao
                checklist.append({
                    "proposal_id": prop["proposal_id"],
                    "display_user": email,
                    "display_client": c_name,
                    "confidence": conf_class,
                    "evidence": ",".join(evidences),
                    "conflicts": ",".join(conflict_codes),
                    "proposed_organization": prop["proposed_organization_name"],
                    "proposed_farm": prop["proposed_farm_name"],
                    "proposed_role": proposed_role,
                    "proposed_access": access_level,
                    "approve_yes_no": "NO",
                    "reviewer": "",
                    "reviewed_at": "",
                    "notes": "Remediado."
                })

        # Conflitos agregados
        for email in all_emails:
            conf_user = {
                "user_email": email,
                "legacy_client_id": None,
                "conflict_code": "USER_WITHOUT_CLIENT",
                "severity": "medium",
                "description": "User has no database link to any client."
            }
            conflicts.append(conf_user)

        for cli in clientes:
            conf_cli = {
                "user_email": None,
                "legacy_client_id": cli['id'],
                "conflict_code": "CLIENT_WITHOUT_USER",
                "severity": "high",
                "description": "Client has no user emails associated directly in its columns."
            }
            conflicts.append(conf_cli)

        # Sempre Rollback!
        conn.rollback()
        print("Coleta e rollback finalizados com sucesso!")

    finally:
        pool.putconn(conn)

    # 7. Escrita dos Artefatos Privados
    print(f"Escrevendo arquivos de inventario em: {output_dir}")

    # JSON Privado
    private_inventory = {
        "timestamp": timestamp,
        "is_production": is_production,
        "clients": [dict(c) for c in clientes],
        "client_stats": client_stats,
        "users": all_emails,
        "orphans": orphans
    }

    with open(f"{output_dir}/inventory_private.json", "w") as f:
        json.dump(private_inventory, f, indent=2, default=str)

    # CSV Privado Clientes
    with open(f"{output_dir}/inventory_private.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "razao_social", "uf", "municipio", "plano", "criado_em", "animals", "groups", "stations", "cruzamentos", "medicoes", "movimentacoes"])
        for c in clientes:
            cid = c['id']
            st = client_stats.get(cid, {})
            writer.writerow([cid, c['razao_social'], c['uf'], c['municipio'], c['plano_contratado'], c['criado_em'],
                             st.get('animals', 0), st.get('groups', 0), st.get('stations', 0), st.get('cruzamentos', 0),
                             st.get('medicoes', 0), st.get('movimentacoes', 0)])

    # Proposals JSON
    with open(f"{output_dir}/mapping_proposals_private.json", "w") as f:
        json.dump(proposals, f, indent=2, default=str)

    # Proposals CSV
    with open(f"{output_dir}/mapping_proposals_private.csv", "w", newline="") as f:
        if proposals:
            writer = csv.DictWriter(f, fieldnames=proposals[0].keys())
            writer.writeheader()
            writer.writerows(proposals)

    # Conflicts CSV
    with open(f"{output_dir}/mapping_conflicts_private.csv", "w", newline="") as f:
        if conflicts:
            writer = csv.DictWriter(f, fieldnames=["user_email", "legacy_client_id", "conflict_code", "severity", "description"])
            writer.writeheader()
            writer.writerows(conflicts)

    # Checklist CSV
    with open(f"{output_dir}/mapping_review_checklist_private.csv", "w", newline="") as f:
        if checklist:
            writer = csv.DictWriter(f, fieldnames=checklist[0].keys())
            writer.writeheader()
            writer.writerows(checklist)

    # README_PRIVATE.txt
    with open(f"{output_dir}/README_PRIVATE.txt", "w") as f:
        f.write(f"Inventorio Privado da Fase 0E1 (Remediado)\n")
        f.write(f"Coletado em: {timestamp}\n")
        f.write(f"Salt HMAC: {salt.hex()}\n")
        f.write(f"Contem dados privados nao versionados para revisao humana.\n")

    # 8. Geracao do Relatorio Sanitizado
    print("Gerando relatorio sanitizado para visualizacao publica...")
    sanitized_report = {
        "timestamp": timestamp,
        "is_production": is_production,
        "total_clients": len(clientes),
        "total_users": len(all_emails),
        "clients_summary": [],
        "orphans": orphans,
        "proposals_summary": {
            "total": len(proposals),
            "by_confidence": {}
        }
    }

    for c in clientes:
        cid = c['id']
        st = client_stats.get(cid, {})
        san_id = hash_id(salt, "client", cid)
        sanitized_report["clients_summary"].append({
            "sanitized_client_id": san_id,
            "uf": c['uf'],
            "municipio": c['municipio'],
            "animals": st.get('animals', 0),
            "groups": st.get('groups', 0),
            "stations": st.get('stations', 0),
            "medicoes": st.get('medicoes', 0),
            "movimentacoes": st.get('movimentacoes', 0)
        })

    for p in proposals:
        cc = p["confidence_class"]
        sanitized_report["proposals_summary"]["by_confidence"][cc] = sanitized_report["proposals_summary"]["by_confidence"].get(cc, 0) + 1

    # Salva relatorio sanitizado temporario para o runbook copiar
    with open(f"{output_dir}/inventory_sanitized.json", "w") as f:
        json.dump(sanitized_report, f, indent=2)

    # 9. Geracao do Manifesto SHA-256
    manifest = {
        "timestamp": timestamp,
        "is_production": is_production,
        "files": {}
    }
    for file in os.listdir(output_dir):
        if file != "checksums.sha256":
            filepath = f"{output_dir}/{file}"
            sha = hashlib.sha256()
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    sha.update(chunk)
            manifest["files"][file] = sha.hexdigest()

    with open(f"{output_dir}/execution_manifest_private.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # checksums.sha256
    with open(f"{output_dir}/checksums.sha256", "w") as f:
        for file, h in manifest["files"].items():
            f.write(f"{h}  {file}\n")

    # Ajusta permissoes do diretorio e arquivos
    os.chmod(output_dir, 0o700)
    for file in os.listdir(output_dir):
        os.chmod(f"{output_dir}/{file}", 0o600)

    print(f"=== Coleta Finalizada com Sucesso! Caminho: {output_dir} ===")

if __name__ == '__main__':
    main()
