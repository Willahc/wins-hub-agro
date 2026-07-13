-- Validação do Banco Restaurado na Fase 0C
\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
  v_count integer;
BEGIN
  -- 1. Verifica se todas as tabelas do schema foundation estão presentes
  SELECT count(*) INTO v_count 
  FROM information_schema.tables 
  WHERE table_schema = 'foundation';
  IF v_count < 9 THEN
    RAISE EXCEPTION 'ERRO: tabelas da fundação ausentes no banco restaurado. Encontradas apenas %', v_count;
  END IF;

  -- 2. Verifica se os dados sintéticos principais estão íntegros
  SELECT count(*) INTO v_count FROM foundation.organizations;
  IF v_count = 0 THEN
    RAISE EXCEPTION 'ERRO: nenhuma organização encontrada no banco restaurado';
  END IF;

  SELECT count(*) INTO v_count FROM foundation.audit_events;
  IF v_count = 0 THEN
    RAISE EXCEPTION 'ERRO: nenhuma auditoria encontrada no banco restaurado';
  END IF;

  RAISE NOTICE 'VALIDACAO RESTORE OK: Banco restaurado possui tabelas e dados populados.';
END;
$$;

COMMIT;
