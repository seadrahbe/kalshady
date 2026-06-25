-- ShadyPredict Phase 0 test fixtures.
-- Loaded into a fresh shadybank DB (which the compose file inits with schema only, no testdata).
-- Creates: one funded test bettor (with a card + known TOTP secret) and the ShadyPredict
-- house/merchant account (with a card + PIN). Idempotent-ish: safe to re-run after a wipe.

DO $$
DECLARE
  cust_id  int;
  acct_id  int;
  house_id int;
BEGIN
  -- ---- Test bettor (a normal customer who already holds some shadybucks) ----
  INSERT INTO customers (name) VALUES ('Test Bettor') RETURNING id INTO cust_id;
  INSERT INTO accounts (customer_id, name, balance, available)
    VALUES (cust_id, 'Test Bettor', 100.00, 100.00) RETURNING id INTO acct_id;
  -- Card. expires/dd only matter for the magstripe path; we use pan+otp, so values are arbitrary.
  INSERT INTO cards (pan, account_id, name, expires, dd1, dd2, status)
    VALUES ('8997000000000001', acct_id, 'BETTOR/TEST', '3012', 'ABCDEF', 123456, 'activated');
  -- Known TOTP secret so the test can generate valid OTPs with pyotp (base32 'JBSWY3DPEHPK3PXP').
  INSERT INTO secrets (account_id, type, secret)
    VALUES (acct_id, 'totp', 'JBSWY3DPEHPK3PXP');
  -- Also a PIN, so tests can read the bettor's bank balance without burning OTP rate limit.
  INSERT INTO secrets (account_id, type, secret)
    VALUES (acct_id, 'password', '1111');

  -- ---- Test bettor 2 (for payout-split tests) ----
  INSERT INTO customers (name) VALUES ('Test Bettor 2') RETURNING id INTO cust_id;
  INSERT INTO accounts (customer_id, name, balance, available)
    VALUES (cust_id, 'Test Bettor 2', 100.00, 100.00) RETURNING id INTO acct_id;
  INSERT INTO cards (pan, account_id, name, expires, dd1, dd2, status)
    VALUES ('8997000000000003', acct_id, 'BETTOR2/TEST', '3012', 'ABCDEF', 222333, 'activated');
  INSERT INTO secrets (account_id, type, secret) VALUES (acct_id, 'totp', 'JBSWY3DPEHPK3PXP');
  INSERT INTO secrets (account_id, type, secret) VALUES (acct_id, 'password', '1111');

  -- ---- ShadyPredict house / merchant account ----
  -- Not partner/admin/special: mirrors the self-funded production design (can't overdraft).
  INSERT INTO accounts (name, balance, available)
    VALUES ('ShadyPredict House', 0.00, 0.00) RETURNING id INTO house_id;
  INSERT INTO cards (pan, account_id, name, expires, dd1, dd2, status)
    VALUES ('8997000000000002', house_id, 'SHADYPREDICT/HOUSE', '3012', 'ABCDEF', 654321, 'activated');
  -- PIN login: secret type 'password' compared as plaintext when logging in with pin=...
  INSERT INTO secrets (account_id, type, secret)
    VALUES (house_id, 'password', '4242');

  RAISE NOTICE 'SEEDED bettor_account=% house_account=%', acct_id, house_id;
END $$;
