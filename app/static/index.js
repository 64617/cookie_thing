const im_elem = document.getElementById('derpi-img')
const id_elem = document.getElementById('derpi-id')
const desc_elem = document.getElementById('desc')
const error_e = document.getElementById('error-desc')
const submit_e = document.getElementById('submit-button')
const wc_elem = document.getElementById('word-count')
const ts_elem = document.getElementById('timestamp')
const tags_e = document.getElementById('tag-dump')
const id = +id_elem.innerHTML

function appendtext(s) {
	desc_elem.value += s+' ';
	checkWordLen()
}
function addtag(s) {
	const linked_tag = document.createElement('a')
	linked_tag.href = '#'
	linked_tag.innerHTML = s;
	linked_tag.onclick = e => {
		e.preventDefault()
		appendtext(s)
	}
	tags_e.appendChild(linked_tag)
	linked_tag.insertAdjacentHTML('afterend', '&nbsp;')
}
async function showImage() {
	try {
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
