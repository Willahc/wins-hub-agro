-- Validação das Roles e Grants pós-restauração da Fase 0C
\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
  -- 1. Validações globais de atributos das roles
  IF EXISTS (
      SELECT 1 FROM pg_roles 
      WHERE rolname IN ('wins_agro_migrator', 'wins_agro_app', 'wins_agro_readonly')
        AND (rolsuper OR rolcreatedb OR rolcreaterole)
  ) THEN 
      RAISE EXCEPTION 'ERRO: Roles de aplicação ou migração possuem atributos excessivos (Superuser/CreateDB/CreateRole)';
  END IF;

  -- 2. PUBLIC não deve possuir privilégios no schema foundation ou seus objetos
  IF EXISTS (
    SELECT 1 FROM pg_namespace n,
      LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) acl
    WHERE n.nspname='foundation' AND acl.grantee=0
  ) THEN
    RAISE EXCEPTION 'ERRO: Privilégio PUBLIC detectado no schema foundation';
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace,
      LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) acl
    WHERE n.nspname='foundation' AND c.relkind IN ('r','S') AND acl.grantee=0
  ) THEN 
    RAISE EXCEPTION 'ERRO: Privilégio PUBLIC detectado em tabelas/sequences do schema foundation'; 
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace,
      LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl
    WHERE n.nspname='foundation' AND acl.grantee=0
  ) THEN 
    RAISE EXCEPTION 'ERRO: Privilégio PUBLIC detectado em funções do schema foundation'; 
  END IF;

  -- 3. Validações específicas para wins_agro_app
  -- USAGE no schema
  IF NOT has_schema_privilege('wins_agro_app', 'foundation', 'USAGE') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_app não possui USAGE no schema foundation';
  END IF;
  -- Não pode criar objetos no schema
  IF has_schema_privilege('wins_agro_app', 'foundation', 'CREATE') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_app possui permissão de CREATE no schema foundation';
  END IF;
  -- DML permitido nas tabelas operacionais
  IF NOT has_table_privilege('wins_agro_app', 'foundation.app_users', 'INSERT') 
     OR NOT has_table_privilege('wins_agro_app', 'foundation.app_users', 'SELECT') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_app sem permissões DML necessárias';
  END IF;
  -- Apenas INSERT no log de auditoria, sem UPDATE ou DELETE
  IF NOT has_table_privilege('wins_agro_app', 'foundation.audit_events', 'INSERT') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_app sem permissão de INSERT em foundation.audit_events';
  END IF;
  IF has_table_privilege('wins_agro_app', 'foundation.audit_events', 'UPDATE') 
     OR has_table_privilege('wins_agro_app', 'foundation.audit_events', 'DELETE') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_app com permissão de escrita indevida (UPDATE/DELETE) em foundation.audit_events';
  END IF;
  -- Não pode executar funções privilegiadas de bootstrap/rollback
  IF has_function_privilege('wins_agro_app', 'foundation.process_legacy_mapping(jsonb,boolean)', 'EXECUTE') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_app pode executar foundation.process_legacy_mapping';
  END IF;
  IF has_function_privilege('wins_agro_app', 'foundation.revoke_legacy_mapping(uuid,uuid,uuid,text,uuid,uuid,boolean)', 'EXECUTE') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_app pode executar foundation.revoke_legacy_mapping';
  END IF;

  -- 4. Validações específicas para wins_agro_readonly
  -- USAGE no schema
  IF NOT has_schema_privilege('wins_agro_readonly', 'foundation', 'USAGE') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_readonly não possui USAGE no schema foundation';
  END IF;
  -- SELECT nas tabelas
  IF NOT has_table_privilege('wins_agro_readonly', 'foundation.organizations', 'SELECT') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_readonly sem permissão de SELECT';
  END IF;
  -- Não pode escrever em tabelas
  IF has_table_privilege('wins_agro_readonly', 'foundation.organizations', 'INSERT')
     OR has_table_privilege('wins_agro_readonly', 'foundation.organizations', 'UPDATE')
     OR has_table_privilege('wins_agro_readonly', 'foundation.organizations', 'DELETE') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_readonly possui privilégios de escrita (DML) em foundation.organizations';
  END IF;
  -- Não pode executar funções de mutação
  IF has_function_privilege('wins_agro_readonly', 'foundation.prevent_published_version_mutation()', 'EXECUTE') THEN
     RAISE EXCEPTION 'ERRO: wins_agro_readonly pode executar trigger de mutação';
  END IF;

  -- 5. Validações específicas para wins_agro_migrator
  -- Deve possuir USAGE no schema
  IF NOT has_schema_privilege('wins_agro_migrator', 'foundation', 'USAGE') THEN
    RAISE EXCEPTION 'ERRO: wins_agro_migrator não possui USAGE no schema';
  END IF;
  -- Não deve ser superuser nem ter CREATEDB/CREATEROLE (já verificado acima)
  
  RAISE NOTICE 'VALIDACAO ROLES OK: Todas as regras de menor privilégio e grants foram comprovadas com sucesso!';
END;
$$;

COMMIT;
