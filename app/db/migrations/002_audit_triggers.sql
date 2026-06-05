-- ============================================================
-- Audit triggerlari — har INSERT/UPDATE/DELETE avtomatik audit_logs ga yoziladi.
-- Actor (kim qildi) `app.actor_id` sessiya o'zgaruvchisidan olinadi:
--   ulanishda:  SET LOCAL app.actor_id = '<users.id>';
-- ============================================================

BEGIN;

CREATE OR REPLACE FUNCTION fn_audit() RETURNS TRIGGER AS $$
DECLARE
    v_actor BIGINT;
BEGIN
    v_actor := NULLIF(current_setting('app.actor_id', true), '')::BIGINT;

    IF (TG_OP = 'INSERT') THEN
        INSERT INTO audit_logs(actor_id, action, entity_type, entity_id, after_data)
        VALUES (v_actor, TG_OP, TG_TABLE_NAME, NEW.id::TEXT, to_jsonb(NEW));
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO audit_logs(actor_id, action, entity_type, entity_id, before_data, after_data)
        VALUES (v_actor, TG_OP, TG_TABLE_NAME, NEW.id::TEXT, to_jsonb(OLD), to_jsonb(NEW));
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO audit_logs(actor_id, action, entity_type, entity_id, before_data)
        VALUES (v_actor, TG_OP, TG_TABLE_NAME, OLD.id::TEXT, to_jsonb(OLD));
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Audit qilinadigan jadvallar (pul bilan bog'liq bo'lganlar)
CREATE TRIGGER trg_audit_transactions
    AFTER INSERT OR UPDATE OR DELETE ON transactions
    FOR EACH ROW EXECUTE FUNCTION fn_audit();

CREATE TRIGGER trg_audit_debts
    AFTER INSERT OR UPDATE OR DELETE ON debts
    FOR EACH ROW EXECUTE FUNCTION fn_audit();

CREATE TRIGGER trg_audit_debt_payments
    AFTER INSERT OR UPDATE OR DELETE ON debt_payments
    FOR EACH ROW EXECUTE FUNCTION fn_audit();

CREATE TRIGGER trg_audit_wallets
    AFTER INSERT OR UPDATE OR DELETE ON wallets
    FOR EACH ROW EXECUTE FUNCTION fn_audit();

CREATE TRIGGER trg_audit_funds
    AFTER INSERT OR UPDATE OR DELETE ON funds
    FOR EACH ROW EXECUTE FUNCTION fn_audit();

COMMIT;
