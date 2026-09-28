export const regions=['Andaman and Nicobar Islands','Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chandigarh','Chhattisgarh','Dadra and Nagar Haveli and Daman and Diu','Delhi','Goa','Gujarat','Haryana','Himachal Pradesh','Jammu and Kashmir','Jharkhand','Karnataka','Kerala','Ladakh','Lakshadweep','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Mizoram','Nagaland','Odisha','Puducherry','Punjab','Rajasthan','Sikkim','Tamil Nadu','Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal'] as const;
// Domains listed by DoLR's national citizen-services directory, checked 2026-09-28.
// Directory verification is not a guarantee that each state portal is currently reachable.
export const landPortals:Record<string,string>={
'Andaman and Nicobar Islands':'https://dweepbhoomi.andamannicobar.gov.in',
'Andhra Pradesh':'https://meebhoomi.ap.gov.in',
'Assam':'https://ilrms.assam.gov.in',
'Bihar':'https://biharbhumi.bihar.gov.in',
'Chandigarh':'https://revenue.chd.gov.in',
'Chhattisgarh':'https://bhuiyan.cg.nic.in',
'Goa':'https://dslr.goa.gov.in',
'Gujarat':'https://anyror.gujarat.gov.in',
'Haryana':'https://jamabandi.nic.in',
'Himachal Pradesh':'https://himbhoomilmk.nic.in',
'Jammu and Kashmir':'https://jkrevenue.nic.in',
'Jharkhand':'https://jharbhoomi.jharkhand.gov.in',
'Karnataka':'https://rdservices.karnataka.gov.in',
'Kerala':'https://revenue.kerala.gov.in',
'Ladakh':'https://landrecords.ladakh.gov.in/lalr',
'Lakshadweep':'https://land.utl.gov.in',
'Madhya Pradesh':'https://mpbhulekhrecords.com',
'Maharashtra':'https://mahabhumi.gov.in',
'Manipur':'https://louchapathap.nic.in',
'Delhi':'https://dlrc.delhi.gov.in',
'Odisha':'https://bhulekh.ori.nic.in',
'Punjab':'https://revenue.punjab.gov.in',
'Rajasthan':'https://apnakhata.raj.nic.in',
'Sikkim':'https://ilrms.sikkim.gov.in/',
'Tamil Nadu':'https://eservices.tn.gov.in',
'Telangana':'https://bhubharati.telangana.gov.in',
'Dadra and Nagar Haveli and Daman and Diu':'https://sugam.dddgov.in',
'Tripura':'https://jami.tripura.gov.in',
'Uttarakhand':'https://bhulekh.uk.gov.in',
'Uttar Pradesh':'https://upbhulekh.gov.in',
'West Bengal':'https://banglarbhumi.gov.in'};
export const regionSource='https://www.india.gov.in/explore-india/facts-of-india/states-ut-districts';
export const landSource='https://dolr.gov.in/en/citizen-centric-services/';
