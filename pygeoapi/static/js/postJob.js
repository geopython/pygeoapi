window.JobExecution = {};
JobExecution.SYNC_EXECUTE = true;

function submitJob(url) {
  let parsedUrl = new URL(url);
  if (JobExecution.SYNC_EXECUTE) {
    parsedUrl.searchParams.set('sync-execute', 'True');
  } else {
    parsedUrl.searchParams.set('async-execute', 'True');
  }
  const elms = document.getElementsByClassName('job-form-input');
  inputs = [];
  for (let i = 0; i < elms.length; i++) {
    let value;
    switch(elms[i].type) {
      case 'checkbox':
        value = elms[i].checked;
        break;
      case 'number':
        // TODO Integer vs float
        value = parseFloat(elms[i].value);
        break;
      default:
        value = elms[i].value;
    }
    inputs.push({id: elms[i].name, value: value});
  }
  data = {"inputs": inputs}
  console.debug({data})
  let xhr = new XMLHttpRequest();
  xhr.onreadystatechange = function() {
    if (xhr.readyState == XMLHttpRequest.OPENED) {
      if (JobExecution.SYNC_EXECUTE) {
        // Sync execution, add waiting message
        let jobResultsSection = document.getElementById('job-results');
        jobResultsSection.innerHTML = null;
        let span = document.createElement('span');
        span.classList.add('toast')
        jobResultsSection.appendChild(span);
        span.innerHTML = 'Running job...';
        jobResultsSection.appendChild(span);
        jobResultsSection.scrollIntoView();
      }
    } else if (xhr.readyState == XMLHttpRequest.DONE && (xhr.status === 201 || xhr.status === 202)) {
      if (this.onreadystatechange) {
        xhr.onreadystatechange = null;
      }
      let jobResultsSection = document.getElementById('job-results');
      jobResultsSection.innerHTML = null;
      let responseLocation = xhr.getResponseHeader("Location");
      const jobId = responseLocation.split('/').pop()
      let h3 = document.createElement('h3');
      h3.innerHTML = jobId;
      let span = document.createElement('span');
      span.classList.add('toast');
      const creationMessage = xhr.status == 201 ? 'is available!' : 'was created!'
      span.innerHTML = 'Job <a target="_blank" href="' + responseLocation + '">' + jobId + '</a> <span class="icon-link inverse"></span> ' + creationMessage + '</span>';
      jobResultsSection.appendChild(h3);
      jobResultsSection.appendChild(span);

      let list = document.createElement('ul');
      jobResultsSection.appendChild(list);

      responseElements = [{
        'innerHTML': 'Job status',
        'target': '_blank',
        'href': responseLocation
      }];
      if (xhr.status === 201) {
        // Synchronous execution, so the results exist too
        responseElements.push({
          'innerHTML': 'Job results',
          'target': '_blank',
          'href': responseLocation + '/results'
        });
      }

      responseElements.forEach(function(el) {
        let li = document.createElement('li');
        let a = document.createElement('a');
        Object.keys(el).forEach(function(prop) {
          a[prop] = el[prop]
        })
        let span = document.createElement('span');
        span.classList.add('icon-link');
        li.append(span);
        li.appendChild(a);
        list.appendChild(li);
      })

      jobResultsSection.appendChild(list);
      jobResultsSection.scrollIntoView();

      return false
    }
  }

  xhr.open('POST', parsedUrl.href, true);
  xhr.setRequestHeader('Content-type', 'application/json');
  xhr.send(JSON.stringify(data));
  return false;
}

function submitButtonClick (event) {
  if (event.name == 'async') {
    JobExecution.SYNC_EXECUTE = false;
  } else if (event.name == 'sync') {
    JobExecution.SYNC_EXECUTE = true;
  }
};
