/*
 *
 * Authors: Bernhard Mallinger <bernhard.mallinger@eox.at>
 *
 * Copyright (c) 2020 Bernhard Mallinger
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use,
 * copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
 * OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 * OTHER DEALINGS IN THE SOFTWARE.
 *
 */


function _showToast(parentId, text) {
  let parent = document.getElementById(parentId);
  parent.innerHTML = null;
  let span = document.createElement('span');
  span.classList.add('toast');
  span.innerHTML = text;
  parent.appendChild(span);
  parent.scrollIntoView();
}

function deleteJob(url) {
  if (!confirm("Do you really want to delete this job?")) {
    return;
  }

  let xhr = new XMLHttpRequest();
  xhr.onreadystatechange = function() {
    if (xhr.readyState == XMLHttpRequest.OPENED) {
      _showToast('action-results', 'Deleting job')
    } else if (xhr.readyState == XMLHttpRequest.DONE && (xhr.status >= 200 && xhr.status < 300)) {
      if (this.onreadystatechange) {
        xhr.onreadystatechange = null;
      }
      _showToast('action-results', 'Job deleted')
      if (!location.pathname.endsWith('jobs')) {
        // Redirect away from deleted job status UI
        setTimeout(function(){
          window.location = location.protocol + '//' + location.hostname + (location.pathname.split('/').slice(0, -1).join('/'));
        }, 2000);
      } else {
        // Refresh
        setTimeout(function() {
          location.reload();
        }, 1000);
      }
    } else if (xhr.readyState == XMLHttpRequest.DONE && (xhr.status >= 400)) {
      _showToast('action-results', 'Error deleting job')
    }
  };

  xhr.open("DELETE", url);
  xhr.send();
}
