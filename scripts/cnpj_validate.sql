-- Validação do dígito verificador do CNPJ (mod-11 oficial Receita).
CREATE OR REPLACE FUNCTION prospeccao.cnpj_dv_ok(c text) RETURNS boolean AS $$
DECLARE
  d text; n int[]; s1 int:=0; s2 int:=0; r1 int; r2 int; dv1 int; dv2 int; i int;
  w1 int[]:=ARRAY[5,4,3,2,9,8,7,6,5,4,3,2];
  w2 int[]:=ARRAY[6,5,4,3,2,9,8,7,6,5,4,3,2];
BEGIN
  d:=regexp_replace(coalesce(c,''),'\D','','g');
  IF length(d)<>14 OR d ~ '^(.)\1{13}$' THEN RETURN false; END IF;   -- 14 díg e não todos iguais
  FOR i IN 1..14 LOOP n[i]:=substr(d,i,1)::int; END LOOP;
  FOR i IN 1..12 LOOP s1:=s1+n[i]*w1[i]; END LOOP;
  r1:=s1%11; dv1:=CASE WHEN r1<2 THEN 0 ELSE 11-r1 END;
  IF n[13]<>dv1 THEN RETURN false; END IF;
  FOR i IN 1..13 LOOP s2:=s2+n[i]*w2[i]; END LOOP;
  r2:=s2%11; dv2:=CASE WHEN r2<2 THEN 0 ELSE 11-r2 END;
  RETURN n[14]=dv2;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
