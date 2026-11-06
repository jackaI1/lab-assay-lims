-- Synthetic records only. Refuse to run this against any existing patient database.
INSERT INTO patient_data (pid, pubpid, uuid, fname, lname, DOB, sex, date)
VALUES (1, 'FICTIONAL-001', UNHEX('00000000000040008000000000000001'), 'Fictional', 'River', '2000-01-01', 'Female', NOW()),
       (2, 'FICTIONAL-002', UNHEX('00000000000040008000000000000002'), 'Fictional', 'Lake', '2000-01-02', 'Male', NOW());
INSERT INTO documents (id, uuid, type, size, date, revision, url, mimetype, owner, foreign_id, docdate, name, path_depth)
VALUES (1, UNHEX('00000000000040008000000000000011'), 'file_url', 64, NOW(), NOW(), 'file:///var/www/localhost/htdocs/openemr/sites/default/documents/1/fictional-lab.txt', 'text/plain', 1, 1, CURRENT_DATE(), 'fictional-lab.txt', 1),
       (2, UNHEX('00000000000040008000000000000012'), 'file_url', 64, NOW(), NOW(), 'file:///var/www/localhost/htdocs/openemr/sites/default/documents/1/fictional-referral.txt', 'text/plain', 1, 1, CURRENT_DATE(), 'fictional-referral.txt', 1),
       (3, UNHEX('00000000000040008000000000000013'), 'file_url', 64, NOW(), NOW(), 'file:///var/www/localhost/htdocs/openemr/sites/default/documents/2/fictional-other.txt', 'text/plain', 1, 2, CURRENT_DATE(), 'fictional-other.txt', 1);
INSERT INTO categories_to_documents (category_id, document_id) VALUES (2,1), (3,2), (2,3);

-- OpenEMR uses this shared counter for new documents and other records.
UPDATE sequences SET id = GREATEST(id, 1000);
