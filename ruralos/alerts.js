export function freshness(checkedAt,reviewBy,category,now=Date.now()) {
 const checked=Date.parse(checkedAt),review=Date.parse(reviewBy);
 if(!Number.isFinite(now)||!Number.isFinite(checked)||!Number.isFinite(review)||checked>now+300000||review<=checked)return 'Needs recheck';
 return now>=review?'Needs recheck':category==='travel_deal'?'Fare snapshot':'Research lead';
}
if(typeof document!=='undefined'){
 const refresh=()=>{for(const el of document.querySelectorAll('[data-review-by]'))el.textContent=freshness(el.dataset.checkedAt,el.dataset.reviewBy,el.dataset.category);};
 refresh();setInterval(refresh,30000);document.addEventListener('visibilitychange',refresh);
}
