-- 기존 DB에 TCHDHC001 만 있을 때 한 번 실행 (이미 변경됐으면 생략)
ALTER TABLE IF EXISTS public."TCHDHC001"
  RENAME TO "그룹멤버십계열사기초데이터검증";
