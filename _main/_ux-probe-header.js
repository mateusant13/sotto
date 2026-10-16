(function(){
  var ids=['theme-button','theme-chevron','font-smaller-button','font-larger-button','tune-button','panel-pause-button','hide-button'];
  var out={theme:document.documentElement.getAttribute('data-theme')};
  out.controls = ids.map(function(id){var e=document.getElementById(id); if(!e) return {id:id,present:false}; var r=e.getBoundingClientRect(); var cs=getComputedStyle(e); return {id:id,present:true,x:+r.x.toFixed(2),y:+r.y.toFixed(2),w:+r.width.toFixed(2),h:+r.height.toFixed(2),color:cs.color,borderColor:cs.borderColor,background:cs.backgroundColor};});
  var w=document.querySelector('.wordmark'); if(w){var r=w.getBoundingClientRect(); out.wordmark={x:+r.x.toFixed(2),y:+r.y.toFixed(2),w:+r.width.toFixed(2),h:+r.height.toFixed(2),text:w.textContent.trim()};}
  var p=document.querySelector('.panel'); var cs=getComputedStyle(p); out.panel={borderTop:cs.borderTopWidth,borderRight:cs.borderRightWidth,borderBottom:cs.borderBottomWidth,borderLeft:cs.borderLeftWidth,radius:cs.borderRadius,boxShadow:cs.boxShadow==='none'?null:cs.boxShadow.slice(0,70)};
  var cb=document.querySelector('.captions__body'); var cbs=cb?getComputedStyle(cb):null; out.captionsBody=cbs?{border:cbs.border,boxShadow:cbs.boxShadow==='none'?null:cbs.boxShadow.slice(0,60)}:null;
  var bar=document.querySelector('.captions__bar'); out.barHTML=bar?bar.innerHTML.replace(/\s+/g,' ').trim().slice(0,260):null;
  var hl=document.querySelector('.history__label'); out.historyLabel=!!hl;
  var ht=document.getElementById('history-toggle'); out.historyToggle=!!ht;
  var ll=document.getElementById('live-label'); out.liveLabel=!!ll;
  return out;
})()