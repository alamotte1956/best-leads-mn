"""State-specific consumer information; notices do not certify legal compliance."""
from flask import Blueprint, abort, render_template
from national_markets import STATES, enabled

state_notices = Blueprint('state_notices',__name__)
REVIEWED_ON = 'November 2, 2026'
NOTICES = {
 'minnesota': {
  'points': (
   'Minnesota residential building, remodeling and roofing license requirements depend on the work. A contractor registration number is not a residential contractor license. Check the applicable DLI license and its scope before hiring.',
   'Insurance-funded residential roofing contracts can carry specific cancellation rights following a denied claim. Review the required notices with the contractor; this website does not replace them.',
  ),
  'sources': (
   ('Minnesota DLI: residential contractor licensing','https://www.dli.mn.gov/business/residential-contractors/residential-contractor-licensing'),
   ('Minnesota DLI: license and registration lookup','https://dli.mn.gov/license-and-registration-lookup'),
   ('Minnesota Statutes: residential roofing cancellation rights','https://www.revisor.mn.gov/statutes/2026/cite/326B.811'),
  )},
 'texas': {
  'points': (
   'Verify the credentials required for the specific trade and local jurisdiction. Non-exempt mold assessment and remediation require TDLR licensing, and Texas restricts conflicts between assessment and remediation on the same project.',
   'A contractor doing the work cannot also act as your public insurance adjuster on that claim. Texas prohibits contractor offers to waive, rebate or absorb a property insurance deductible. No such service or deductible waiver is offered here.',
  ),
  'sources': (
   ('Texas Attorney General: mold remediation and licensing','https://www.texasattorneygeneral.gov/consumer-protection/home-real-estate-and-travel/mold-remediation'),
   ('Texas Department of Insurance: roofing and insurance rules','https://www.tdi.texas.gov/consumer/storms/roofing-and-insurance-know-the-law.html'),
  )},
 'florida': {
  'points': (
   'Check the contractor and the qualified business through Florida DBPR, including the license classification and geographic scope. Approval on this platform does not expand a license or authorize an unlicensed trade.',
   'Florida restricts insurance deductible waivers and incentives tied to roof inspections or insurance claims. Insurance-related repair agreements require appropriate estimates and notices. Discuss coverage with your insurer or an appropriately licensed professional; this platform does not interpret policies or negotiate claims.',
  ),
  'sources': (
   ('Florida DBPR: construction business licensing and verification','https://www2.myfloridalicense.com/construction-industry/construction-industry-business-information/'),
   ('Florida Department of Financial Services: contractor and roofing consumer protections','https://myfloridacfo.com/division/consumers/storm/contractor-residential-property-faqs'),
  )},
 'north-carolina': {
  'points': (
   'North Carolina generally requires a licensed general contractor for projects valued at $40,000 or more. Separate trade licenses and local permits may apply below that amount. Check the license classification and monetary limitation for your project.',
   'Use a written agreement and review applicable cancellation notices, particularly for contracts signed at home or away from the seller’s normal business location. A website request is not that construction agreement.',
  ),
  'sources': (
   ('North Carolina Licensing Board for General Contractors: consumer FAQs','https://www.nclbgc.org/faq-consumers/'),
   ('North Carolina Department of Justice: safe rebuilding and contract protections','https://ncdoj.gov/helene/safe-to-rebuild/'),
  )},
 'georgia': {
  'points': (
   'Georgia licenses residential and general contractors, while certain limited specialty work is exempt from those particular licenses. An exemption does not authorize regulated plumbing, electrical or conditioned-air work and does not remove local code or permit requirements.',
   'Verify the business, the individual license holder where required, the authorized scope and local requirements before signing a written agreement. A general-contractor credential is not a substitute for a required specialty-trade license.',
  ),
  'sources': (
   ('Georgia Secretary of State: specialty contractor scope and exemptions','https://sos.ga.gov/page/traditional-specialty-contractors-policy-statements'),
   ('Georgia Attorney General Consumer Ed: home improvement and license checks','https://consumered.georgia.gov/your-home/home-improvement'),
  )},
 'wisconsin': {
  'points': (
   'For covered one- and two-family work requiring permits, Wisconsin dwelling-contractor and qualifier credentials may be required. Confirm the applicable DSPS credentials, permit responsibility and insurance rather than treating a business listing as a license.',
   'Wisconsin home-improvement and insurance-related exterior-repair rules provide specific contract and cancellation protections. Contractors cannot promise to pay your insurance deductible or negotiate your insurance claim on your behalf. Review the written notices before signing.',
  ),
  'sources': (
   ('Wisconsin DATCP: home improvement requirements and cancellation rights','https://datcp.wi.gov/Pages/Publications/HI-ConsumerTips136.aspx'),
   ('Wisconsin DATCP: flood repair and insurance protections','https://datcp.wi.gov/Pages/News_Media/20250814ConsumersShouldSeekTrustworthyContractorsAfterFloodDamage.aspx'),
  )},
 'indiana': {
  'points': (
   'Indiana general-contractor requirements are largely local. Check the city or county building department for the work location; state-regulated trades such as plumbing require the appropriate professional credentials. A general business registration does not establish trade qualification.',
   'Obtain a written home-improvement agreement with the work, price, timing and responsible business identified, and review applicable cancellation and insurance-related requirements. This website is a matching platform, not the improvement contractor or an insurance representative.',
  ),
  'sources': (
   ('Indiana state government: construction and local licensing guidance','https://www.in.gov/core/business_guide.html'),
   ('Indiana Professional Licensing Agency: search and verify credentials','https://www.in.gov/pla/license/'),
   ('Monroe County Prosecutor: home-improvement contracts and consumer protection','https://www.monroeprosecutor.us/prevention-education/crimes-against-the-elderly/home-improvement-fraud/'),
  )},
}


def notice_for(value):
    slug = value if value in STATES else next((slug for slug,market in STATES.items() if market[0]==value),None)
    if slug not in NOTICES: return None
    return dict(NOTICES[slug],slug=slug,name=STATES[slug][1],is_open=enabled(slug),reviewed_on=REVIEWED_ON)


@state_notices.app_context_processor
def notice_context(): return {'state_notice':notice_for}


@state_notices.get('/state-notices')
@state_notices.get('/state-notices/<state>')
def show(state=None):
    if state is not None and state not in STATES: abort(404)
    return render_template('state_notices.html',states=STATES,selected_state=state,enabled=enabled)
