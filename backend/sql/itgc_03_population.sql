-- Sampling population for ITGC-03.
-- Every change ticket, including tickets that were not deployed.
-- A ticket has no role. Risk-based sampling treats payments and the general
-- ledger as the critical systems and selects those tickets first.

SELECT
    ticket.ticket_id AS item_id,
    NULL AS role,
    ticket.system
FROM change_tickets AS ticket
ORDER BY ticket.ticket_id;
