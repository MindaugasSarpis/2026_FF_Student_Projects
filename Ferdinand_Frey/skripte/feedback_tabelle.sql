-- Tabelle für das Feedback-Formular (D1-Datenbank sametrain-feedback). Einmalig anlegen:
--   npx wrangler d1 execute sametrain-feedback --remote --file skripte/feedback_tabelle.sql
-- Keine IP-Adressen, nur was im Formular steht.
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  zeit TEXT NOT NULL,          -- UTC, ISO-Format
  sprache TEXT,                -- de / en
  seite TEXT,                  -- von welcher Seite das Formular aufgerufen wurde
  art TEXT,                    -- lob / fehler / wunsch / sonstiges
  nachricht TEXT NOT NULL,
  email TEXT                   -- freiwillig, nur für Rückfragen
);
