import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
const compose = (args, input) =>
  execFileSync("docker", ["compose", ...args], {
    input,
    encoding: "utf8",
    maxBuffer: 1024 * 1024,
  });
const db = (sql) =>
  compose(
    [
      "exec",
      "-T",
      "mysql",
      "mariadb",
      "-uroot",
      "-pfictional-local-demo",
      "--batch",
      "--skip-column-names",
      "openemr",
    ],
    sql,
  );
if (db("SELECT COUNT(*) FROM patient_data;").trim() !== "0")
  throw new Error(
    "Seed is only allowed in an empty, disposable demo database.",
  );
db(readFileSync("demo/seed.sql", "utf8"));
compose([
  "exec",
  "-T",
  "openemr",
  "sh",
  "-c",
  "mkdir -p /var/www/localhost/htdocs/openemr/sites/default/documents/1 /var/www/localhost/htdocs/openemr/sites/default/documents/2",
]);
for (const [patient, name, text] of [
  [
    "1",
    "fictional-lab.txt",
    "FICTIONAL ONLY: River lab example. No real patient information.\n",
  ],
  [
    "1",
    "fictional-referral.txt",
    "FICTIONAL ONLY: River referral example. Not medical advice.\n",
  ],
  [
    "2",
    "fictional-other.txt",
    "FICTIONAL ONLY: Lake chart. Do not send with River documents.\n",
  ],
]) {
  compose(
    [
      "exec",
      "-T",
      "openemr",
      "sh",
      "-c",
      `cat > /var/www/localhost/htdocs/openemr/sites/default/documents/${patient}/${name}`,
    ],
    text,
  );
  db(
    `UPDATE documents SET size=${Buffer.byteLength(text)} WHERE name='${name}';`,
  );
}
compose([
  "exec",
  "-T",
  "openemr",
  "sh",
  "-c",
  "chown -R apache:apache /var/www/localhost/htdocs/openemr/sites/default/documents/1 /var/www/localhost/htdocs/openemr/sites/default/documents/2",
]);
console.log(
  "Seeded two fictional patients and three fictional text documents.",
);
