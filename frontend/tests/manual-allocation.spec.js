import { test, expect } from "@playwright/test";

test("manual applicant journey and isolated reviewed allocation", async ({ page, request }) => {
  test.skip(process.env.ALLOCATEAI_E2E_FIXTURES !== "1", "Requires a disposable local SQLite instance");
  const health = await (await request.get("/api/health")).json();
  expect(health).toMatchObject({ database:"sqlite", checkpoints:"memory", fixture_mode:true });
  const suffix = Date.now();
  const title = "Isolated browser role " + suffix;
  const email = "browser-" + suffix + "@unit.test";
  const password = "OnlyAnIsolatedBrowserFixture@1";
  async function send(method, path, data, token) {
    const response = await request.fetch("/api" + path, { method, data,
      headers: token ? { Authorization: "Bearer " + token } : undefined });
    expect(response.ok(), method + " " + path + " " + await response.text()).toBeTruthy();
    return response.json();
  }
  const admin = (await send("POST","/auth/login",{
    email:process.env.ADMIN_EMAIL || "admin@allocate.local", password:process.env.ADMIN_PASSWORD
  })).access_token;
  const skills = await send("GET","/skills?q=Python",undefined,admin);
  const skill = skills.skills.find(s => s.name === "Python");
  expect(skill).toBeDefined();
  const today = new Date().toISOString().slice(0,10);
  const link = "https://unit.test/isolated-browser-" + suffix;
  const { ids:[lid] } = await send("POST","/import/listings/commit",[{
    title, organization:"Isolated browser scope", source_name:"Browser test fixture",
    source_url:link, work_mode:"remote", description:"Required Python for the isolated browser fixture.",
    requirements:[{skill_id:skill.id,classification:"required",excerpt:"Required Python"}],
    last_verified:today, rolling:true, status:"open",
  }],admin);
  await send("POST","/admin/listings/" + lid + "/approve",{
    expected_version:1,verification_reference:"Isolated browser fixture"
  },admin);
  const policy = await send("POST","/admin/policies",{
    name:"Isolated browser rule version " + suffix,
    config:{coverage_confirmed:true,scheme:"Isolated browser scope",effective_date:today}
  },admin);
  await send("POST","/admin/policies/" + policy.id + "/approve",undefined,admin);
  const round = await send("POST","/admin/rounds",{
    name:"Isolated browser round " + suffix,scope:"Isolated browser scope",
    policy_id:policy.id,listing_ids:[lid]
  },admin);
  const staffEmail = "placement-" + suffix + "@unit.test";
  const staff = await send("POST","/auth/register",{email:staffEmail,name:"Isolated Placement Tester",password});
  await send("PUT","/admin/staff/" + staff.id,{
    role:"placement", scope:"Isolated browser scope", evidence_reference:"Isolated browser staff grant"
  },admin);
  const placement = (await send("POST","/auth/login",{email:staffEmail,password})).access_token;
  await send("PUT","/rounds/" + round.id + "/capacity",{
    listing_id:lid,seats:1,confirmation_reference:"Isolated browser fixture capacity"
  },placement);

  await page.goto("/");
  await page.getByRole("button",{name:"Create an applicant account",exact:true}).click();
  await page.getByLabel("Full name",{exact:true}).fill("Isolated Browser Applicant");
  await page.getByLabel("Email",{exact:true}).fill(email);
  await page.getByLabel("Password",{exact:true}).fill(password);
  await page.getByRole("button",{name:"Create account",exact:true}).click();
  await expect(page.getByRole("button",{name:"Refresh workspace",exact:true})).toBeEnabled();
  await page.getByRole("button",{name:"Applicant Workspace",exact:true}).click();
  await page.getByLabel("Course or trade",{exact:true}).fill("Isolated course");
  await page.getByLabel(/I consent to use of my own authorized records/).check();
  await page.getByRole("button",{name:"Save profile",exact:true}).click();
  await expect(page.getByText("Profile saved",{exact:true})).toBeVisible();
  await page.getByLabel("Search profile skills",{exact:true}).fill("Python");
  await page.getByRole("combobox",{name:"Canonical skill",exact:true}).selectOption(String(skill.id));
  await page.getByLabel("Exact supporting statement",{exact:true}).fill("Skills: Python");
  await page.getByRole("button",{name:"Save to profile",exact:true}).click();
  await expect(page.getByText("Self-reported evidence saved",{exact:true})).toBeVisible();
  const applicant = await send("POST","/auth/login",{email,password});
  const owner = applicant.access_token;
  const profile = await send("GET","/applicant/profile",undefined,owner);
  expect(profile.profile.course).toBe("Isolated course");
  expect(profile.documents).toEqual([]);
  expect(profile.evidence[0].status).toBe("self_reported");

  await page.getByRole("button",{name:"Internship Explorer",exact:true}).click();
  await expect(page.getByRole("link",{name:"Original application / source"}).filter({ visible:true }).first()).toBeVisible();
  await expect(page.getByRole("link", {name:"Original application / source"})).toHaveAttribute("href", link);
  const match = page.locator("details.pair-detail").filter({hasText:title}).first();
  await match.locator("summary").click();
  await expect(match.getByText("100.0 / 100").first()).toBeVisible();
  await match.getByRole("button",{name:"Explain using verified facts",exact:true}).click();
  await expect(match.getByText(/Accepted exact skill matches: Python/)).toBeVisible();

  await send("POST","/admin/evidence/" + profile.evidence[0].id + "/review",{status:"verified"},admin);
  expect((await request.put("/api/rounds/" + round.id + "/choices",{
    data:{listing_ids:[lid]},headers:{Authorization:"Bearer " + owner}
  })).status()).toBe(404);
  await send("PUT","/admin/rounds/" + round.id + "/participation",{
    applicant_id:applicant.user.id,evidence_reference:"Isolated browser participant consent"
  },admin);
  await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();
  await page.getByRole("button",{name:"Allocation Rounds",exact:true}).click();
  await page.getByRole("combobox",{name:"Active round",exact:true}).selectOption(String(round.id));
  await page.getByRole("combobox",{name:"Add ranked internship",exact:true}).selectOption(String(lid));
  await page.getByRole("button",{name:"Save top-five choices",exact:true}).click();
  await expect(page.getByText("Ranked choices saved",{exact:true})).toBeVisible();
  await send("POST","/admin/rounds/" + round.id + "/freeze",undefined,admin);
  const draft = await send("POST","/admin/rounds/" + round.id + "/allocate",undefined,admin);
  expect(draft.placements).toHaveLength(1);
  expect(await send("GET","/outcomes",undefined,owner)).toEqual([]);
  const adminPage = await page.context().newPage();
  await adminPage.goto("/");
  await adminPage.evaluate(token => sessionStorage.setItem("allocateai-v2-token",token),admin);
  await adminPage.reload();
  await adminPage.getByRole("button",{name:"Evidence & Draft Review",exact:true}).click();
  const card = adminPage.locator("article").filter({hasText:"Draft #" + draft.id + " · Policy"});
  await card.getByLabel(/I reviewed this exact draft/).check();
  await card.getByRole("button",{name:"Approve exact draft",exact:true}).click();
  await card.getByRole("button",{name:"Publish approved results",exact:true}).click();
  await expect(card.getByRole("button",{name:"Publish approved results",exact:true})).toBeDisabled();
  await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();
  await page.getByRole("button",{name:"Published Outcomes",exact:true}).click();
  await expect(page.getByText(title,{exact:false}).first()).toBeVisible();
  expect((await send("GET","/outcomes",undefined,owner))[0].listing.source_url).toBe(link);
  await send("POST","/auth/register",{email:"other-" + email,name:"Isolated Other Applicant",password});
  const other = await send("POST","/auth/login",{email:"other-" + email,password});
  expect(await send("GET","/outcomes",undefined,other.access_token)).toEqual([]);
});
