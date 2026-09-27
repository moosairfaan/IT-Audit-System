-- ITGC-03 Change management
--
-- Objective: A deployed change is approved by someone other than the requester
-- and the deployer, and the approval happens before deployment.
-- Risk: An unapproved or self-approved change can put unreviewed code or
-- configuration into production.
--
-- Population: change tickets that have a deployed_at timestamp.
-- A ticket that was not deployed is outside this test.
-- Exception reasons, which can combine:
--   no approval
--   deployed before approval
--   approver is the requester
--   approver is the deployer

SELECT COUNT(*) AS population_count
FROM change_tickets
WHERE deployed_at IS NOT NULL;

SELECT
    ticket.ticket_id AS exception_id,
    ticket.system,
    ticket.requested_by,
    ticket.approved_by,
    ticket.deployed_by,
    ticket.approved_at,
    ticket.deployed_at,
    ticket.description,
    concat_ws(
        '; ',
        CASE
            WHEN ticket.approved_at IS NULL OR ticket.approved_by IS NULL THEN 'no approval'
        END,
        CASE
            WHEN ticket.approved_at IS NOT NULL AND ticket.deployed_at < ticket.approved_at
            THEN 'deployed before approval'
        END,
        CASE
            WHEN ticket.approved_by IS NOT NULL AND ticket.approved_by = ticket.requested_by
            THEN 'approver is the requester'
        END,
        CASE
            WHEN ticket.approved_by IS NOT NULL AND ticket.approved_by = ticket.deployed_by
            THEN 'approver is the deployer'
        END
    ) AS reason
FROM change_tickets AS ticket
WHERE ticket.deployed_at IS NOT NULL
  AND (
        ticket.approved_at IS NULL
        OR ticket.approved_by IS NULL
        OR ticket.deployed_at < ticket.approved_at
        OR ticket.approved_by = ticket.requested_by
        OR ticket.approved_by = ticket.deployed_by
      )
ORDER BY ticket.ticket_id;
