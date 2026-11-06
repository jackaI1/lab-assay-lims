const url =
  "http://127.0.0.1:8080/openemr/interface/login/login.php?site=default";
let missing = 0;
for (let attempt = 0; attempt < 180; attempt++) {
  let status = "not listening";
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(3000) });
    status = `HTTP ${r.status}`;
    missing = r.status === 404 ? missing + 1 : 0;
    if (r.ok && (await r.text()).includes("authUser")) {
      console.log("OpenEMR login ready.");
      process.exit(0);
    }
  } catch {}
  if (missing >= 3)
    throw new Error("OpenEMR returned 404. Check the demo Apache alias mount.");
  if (attempt % 12 === 0) console.log(`Waiting for OpenEMR: ${status}`);
  await new Promise((resolve) => setTimeout(resolve, 5000));
}
throw new Error("OpenEMR did not finish setup within 15 minutes.");
