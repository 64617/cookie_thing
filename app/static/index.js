const im_elem = document.getElementById('derpi-img')
const id_elem = document.getElementById('derpi-id')
const desc_elem = document.getElementById('desc')
const error_e = document.getElementById('error-desc')
const submit_e = document.getElementById('submit-button')
const wc_elem = document.getElementById('word-count')
const ts_elem = document.getElementById('timestamp')
const tags_e = document.getElementById('tag-dump')
const filter_e = document.getElementById('image-filter')
const id = +id_elem.innerHTML
let char_set;

function setCookie(name,value,days) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days*24*60*60*1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "")  + expires + "; path=/";
}
function getCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for(var i=0;i < ca.length;i++) {
        var c = ca[i];
        while (c.charAt(0)==' ') c = c.substring(1,c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
    }
    return null;
}
function eraseCookie(name) {   
    document.cookie = name +'=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
}

if (getCookie('image_filter') === null) {
	setCookie('image_filter', 'any', 99)
}
const FILTER_LIST = ["any", "NSFW", "NSFL", "SAFE"]
const filter_idx = FILTER_LIST.indexOf(getCookie('image_filter'))
filter_e.options[filter_idx].selected = true;

filter_e.onchange = e => {
	setCookie('image_filter', e.currentTarget.value);
	window.location.reload();
}

function appendtext(s) {
	desc_elem.value += s+' ';
	checkWordLen()
}
function addtag(s) {
	if (char_set.has(s)) {
		s = s.split(' ')
			.map(w => w[0].toUpperCase() + w.substr(1))
			.join(" ");
	}
	const linked_tag = document.createElement('a')
	linked_tag.href = '#'
	linked_tag.innerHTML = s;
	linked_tag.onclick = e => {
		e.preventDefault()
		appendtext(s)
	}
	tags_e.appendChild(linked_tag)
	linked_tag.insertAdjacentHTML('afterend', ' ')
}
async function get_characters() {
	if (localStorage.getItem('char_list') === null) {
		const res = await fetch('/static/character_tags.txt');
		const txt = await res.text();
		localStorage.setItem('char_list', txt.trim());
	}
	return localStorage.getItem('char_list').split('\n')
}
async function showImage() {
	try {
	char_set = new Set(await get_characters())
  const res = await fetch(`https://derpibooru.org/api/v1/json/images/${id}`)
	const json = await res.json();
	const url = json.image.representations.medium;
	im_elem.onload = () => {
		tags_e.style.maxWidth = desc.style.width = im_elem.width;
	}
	im_elem.src = url;
	json.image.tags.forEach(s => addtag(s))
	} catch (e) {
		console.log(e)
		error_e.innerHTML = 'Error (refresh the page):'+e;
		error_e.hidden = false
	}
}
showImage();

function checkWordLen() {
	const s = desc_elem.value.trim()
	const words = s ? s.split(' ').length : 0; // just approx
	wc_elem.innerHTML = words;
	const warning = (words > 49);
	const too_much = (words > 99);
	if (too_much) {
		desc_elem.style.boxShadow = "0 0 4px 1px red"
	} else if (warning) {
		desc_elem.style.boxShadow = "0 0 4px 1px orange"
	} else {
		desc_elem.style.boxShadow = "inherit"
	}
	submit_e.disabled = too_much;
}
desc_elem.addEventListener('input', checkWordLen)

ts_elem.value = (Date.now()/1000)|0;
