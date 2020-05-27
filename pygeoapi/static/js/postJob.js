function submitJob(url) {
  var elms = document.getElementsByClassName('job-form-input');
  inputs = [];
  for (var i = 0; i < elms.length; i++) {
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
  var xhr = new XMLHttpRequest();
  xhr.open('POST', url, true);
  xhr.setRequestHeader('Content-type', 'application/json');
  xhr.onreadystatechange = function() {
    if (this.readyState = this.DONE && (xhr.status == 201 || xhr.status == 202)) {
      if (this.onreadystatechange) {
        xhr.onreadystatechange = null;
      }
      var jobResultsSection = document.getElementById('job-results');
      jobResultsSection.innerHTML = null;
      var responseLocation = xhr.getResponseHeader("Location");
      var jobId = responseLocation.split('/').pop()
      var h3 = document.createElement('h3');
      h3.innerHTML = jobId;
      var span = document.createElement('span');
      span.classList.add('toast')
      span.innerHTML = 'Job <a target="_blank" href="' + responseLocation + '">' + jobId + '</a> <span class="icon-link inverse"></span> was created!</span>';
      jobResultsSection.appendChild(h3);
      jobResultsSection.appendChild(span);

      var list = document.createElement('ul');
      jobResultsSection.appendChild(list);

      responseElements = [
        {'innerHTML': 'Job status', 'target': '_blank', 'href': responseLocation},
        {'innerHTML': 'Job results', 'target': '_blank', 'href': responseLocation + '/results'}
      ]

      responseElements.forEach(function(el) {
        var li = document.createElement('li');
        var a = document.createElement('a');
        Object.keys(el).forEach(function(prop) {
          a[prop] = el[prop]
        })
        var span = document.createElement('span');
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
  data = {"inputs": inputs}
  console.debug({data})
  xhr.send(JSON.stringify(data));
  return false;
}
