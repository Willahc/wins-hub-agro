-- =============================================================================
-- backfill_agro_real_001.sql
-- Produção — WiNS Hub Agro
--
-- OBJETIVO: documentar e aplicar APENAS backfill cadastral real e compatível
--           a partir do legado fazenda.cliente → foundation.operational_farms.
--
-- NÃO faz:
--   - seed sintético de piquetes, estoques, silagem, colheita, clima, autonomia
--   - inventar produtividade, MS, perdas, capacidade, coordenadas, custos
--   - criar segunda fazenda ou alterar public_id / organization_id / memberships
--
-- DIAGNÓSTICO (2026-07-14, produção):
--   foundation.operational_farms: 1 fazenda "Fazenda Demonstração"
--     public_id b0000000-0000-4000-8000-00000000000b (placeholder de acesso)
--   fazenda.cliente id=17: mesmo nome, UF=TO, município=Porto Nacional
--   Módulos agro (pasture/storage/harvest/nutrition/climate): 0 registros
--   Legado animal/reprodução existe (cliente 17) mas NÃO mapeia 1:1 para
--   indicadores agro sem inventar categoria/consumo/MS — portanto NÃO migrado.
--
-- USO:
--   1) Dry-run:  psql ... -v dry_run=1 -f backfill_agro_real_001.sql
--   2) Apply:    psql ... -v dry_run=0 -f backfill_agro_real_001.sql
--   Default dry_run=1 se variável ausente.
-- =============================================================================

\set ON_ERROR_STOP on

DO $$
DECLARE
  v_dry boolean := COALESCE(current_setting('dry_run', true), '1') IN ('1', 'true', 'TRUE', 'yes');
  -- fallback: se -v dry_run não existir no session, assume dry-run
  v_farm_pub uuid := 'b0000000-0000-4000-8000-00000000000b';
  v_org_pub  uuid := 'a0000000-0000-4000-8000-00000000000a';
  v_farm_id bigint;
  v_org_id  bigint;
  v_cli_id  integer;
  v_cli_uf  char(2);
  v_cli_mun text;
  v_updated int := 0;
  v_ignored int := 0;
BEGIN
  -- dry_run via app.setting se setado: SET app.dry_run = '0';
  BEGIN
    v_dry := COALESCE(current_setting('app.dry_run', true), '1') <> '0';
  EXCEPTION WHEN OTHERS THEN
    v_dry := true;
  END;

  RAISE NOTICE '=== backfill_agro_real_001 dry_run=% ===', v_dry;

  SELECT f.id, f.organization_id INTO v_farm_id, v_org_id
    FROM foundation.operational_farms f
    JOIN foundation.organizations o ON o.id = f.organization_id
   WHERE f.public_id = v_farm_pub
     AND o.public_id = v_org_pub;

  IF v_farm_id IS NULL THEN
    RAISE NOTICE 'IGNORADO: fazenda % não encontrada na org %', v_farm_pub, v_org_pub;
    RETURN;
  END IF;

  -- Lookup legado por nome estável + única ocorrência (sem inventar vínculo)
  SELECT c.id, c.uf, c.municipio INTO v_cli_id, v_cli_uf, v_cli_mun
    FROM fazenda.cliente c
   WHERE c.razao_social = 'Fazenda Demonstração'
   ORDER BY c.id
   LIMIT 2;  -- se >1, abortamos por ambiguidade

  -- re-count for ambiguity
  IF (SELECT count(*) FROM fazenda.cliente WHERE razao_social = 'Fazenda Demonstração') <> 1 THEN
    RAISE NOTICE 'IGNORADO: cliente legado ambíguo ou ausente para Fazenda Demonstração (count=%)',
      (SELECT count(*) FROM fazenda.cliente WHERE razao_social = 'Fazenda Demonstração');
    v_ignored := v_ignored + 1;
  ELSIF v_cli_uf IS NULL THEN
    RAISE NOTICE 'IGNORADO: cliente % sem UF', v_cli_id;
    v_ignored := v_ignored + 1;
  ELSE
    -- Apenas preenche state se ainda NULL (não sobrescreve cadastro real)
    IF EXISTS (
      SELECT 1 FROM foundation.operational_farms
       WHERE id = v_farm_id AND state IS NULL
    ) THEN
      RAISE NOTICE 'UPDATE state=% farm_id=% (de cliente_id=% municipio=%)',
        v_cli_uf, v_farm_id, v_cli_id, v_cli_mun;
      IF NOT v_dry THEN
        UPDATE foundation.operational_farms
           SET state = v_cli_uf,
               updated_at = now()
         WHERE id = v_farm_id
           AND state IS NULL
           AND organization_id = v_org_id;
        GET DIAGNOSTICS v_updated = ROW_COUNT;
      ELSE
        v_updated := 1; -- contagem projetada
      END IF;
    ELSE
      RAISE NOTICE 'IGNORADO: state já preenchido farm_id=%', v_farm_id;
      v_ignored := v_ignored + 1;
    END IF;
  END IF;

  -- Explicitamente NÃO migrar (relatório):
  RAISE NOTICE 'NÃO MIGRADOS (sem destino agro sem inventar campos):';
  RAISE NOTICE '  fazenda.animal cliente_id=% → count=%', v_cli_id,
    (SELECT count(*) FROM fazenda.animal WHERE cliente_id = v_cli_id);
  RAISE NOTICE '  fazenda.movimentacao → count=%',
    (SELECT count(*) FROM fazenda.movimentacao WHERE cliente_id = v_cli_id);
  RAISE NOTICE '  fazenda.medicao (via animal) → count=%',
    (SELECT count(*) FROM fazenda.medicao m
       JOIN fazenda.animal a ON a.id = m.animal_id WHERE a.cliente_id = v_cli_id);
  RAISE NOTICE '  pasture/storage/harvest/nutrition/climate → todos 0 (nada a backfillar)';

  RAISE NOTICE 'RESULTADO: updated=% ignored=% dry_run=%', v_updated, v_ignored, v_dry;

  IF v_dry THEN
    RAISE NOTICE 'Dry-run concluído — nenhuma alteração persistida.';
  END IF;
END $$;
