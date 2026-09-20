# Third-party notices

The root [MIT license](LICENSE) applies to original Contour code and original project-created materials. It does not replace the licenses of the dependencies or source photographs below. Keep their attribution, license texts, and applicable source-availability terms with redistributions. Installed Python environments, compiler downloads, native build products, and private test artifacts are not part of the source release.

## Vendored libraries

| Material | Version and source | License and included notice |
|---|---|---|
| `backend/vendor/CImg.h` | CImg 3.5.5, [GreycLab/CImg](https://github.com/GreycLab/CImg/blob/v.3.5.5/CImg.h); unmodified upstream header | CeCILL-C; complete text in [CImg-LICENSE.txt](backend/vendor/CImg-LICENSE.txt) |
| `backend/vendor/zxing-2.3.0.zip` | [ZXing-C++ 2.3.0](https://github.com/zxing-cpp/zxing-cpp/tree/v2.3.0); upstream source archive | Apache-2.0; upstream `LICENSE` retained inside the archive. A copy of the Apache-2.0 terms is also included below. |

CImg's library header is licensed separately from its upstream examples, plugins and documentation. Contour vendors the header, not those other CImg materials. Its [upstream license explanation](https://cimg.eu/) and the included full license remain authoritative. Relevant C++ exports include `CImg.h`, the Contour adapter, and the CeCILL-C text. Keep the covered source available when redistributing a compiled CImg-based program, as required by that license. Do not label the CImg header itself as MIT.

Barcode exports include the complete pinned ZXing source tree and its license. They build the reader locally and do not download another source tree during the export build. Contour's bridge and adapter source files are original project code; this does not change the upstream library licenses.

## Runtime and build dependencies

`requirements.txt` installs FastAPI, Uvicorn, HTTPX, OpenCV-Python, NumPy, Pillow, ZXing-C++, and pytest. Those installed distributions retain their own licenses and bundled third-party notices. They are not copied into the source release. A distribution that bundles an environment or executable must retain the notices for its actual dependency builds, including OpenCV's codec dependencies.

OpenCV is an external build prerequisite for exported programs. The optional native-check setup uses [OpenCV 4.12.0](https://github.com/opencv/opencv/tree/4.12.0), whose [license](https://github.com/opencv/opencv/blob/4.12.0/LICENSE) is Apache-2.0. No OpenCV binary, compiler, or build cache is distributed in this repository.

## Photographs and external graphics

The originals and their source links are documented in [examples/SOURCES.md](examples/SOURCES.md). The original filenames below, derived `examples/object-tests/photo-*` images, and images embedded in the saved-project pack retain the same relevant image license.

| Material | Attribution/source | License or source statement |
|---|---|---|
| `examples/smarties.png` and candy derivatives | [OpenCV sample image](https://github.com/opencv/opencv/blob/4.x/samples/data/smarties.png) | Distributed in the OpenCV source repository under its Apache-2.0 license; preserve upstream attribution. |
| `examples/coins.png` and coin derivatives | Brooklyn Museum, via [scikit-image coins](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.coins) | No known copyright restrictions according to the dataset documentation. |
| `examples/red-apple.jpg` and apple derivatives | Abhijit Tembhekar, [Red Apple](https://commons.wikimedia.org/wiki/File:Red_Apple.jpg) | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) |
| `examples/tennis-ball.png` and tennis derivatives | KS, derived from Christian “VisualBeo” Horvat, [Tennisball2](https://commons.wikimedia.org/wiki/File:Tennisball2.png) | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). Redistributed adaptations of the image retain this license. |
| `examples/horse.png` | Andreas Preuss (“marauder”), via [scikit-image horse](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.horse) | CC0 according to the dataset documentation. |
| `examples/green-shapes.png` | [Green shapes](https://commons.wikimedia.org/wiki/File:Green_shapes.png) | File page identifies simple geometry as public domain; conflicting structured metadata identifies Neha Chandrasekaran and CC BY-SA 4.0. Contour retains that attribution and the [CC BY-SA 4.0 link](https://creativecommons.org/licenses/by-sa/4.0/) conservatively, without claiming the metadata establishes authorship. |

The photo object sets contain a size-limited base copy, a 180-degree rotation, and an artificial blank negative. Resizing, rotation and PNG encoding are changes from the source photograph. Credits and image licenses remain applicable to the photographic derivatives, including those embedded in saved project JSON. The blank negatives and programmatically constructed 2D teaching images are original Contour materials. Their inclusion does not imply independent real-world validation.

The optional local `artifacts/` directory contains additional validation photographs and derived previews, with separate per-file manifests. That directory is excluded from this source release; its additional photos are not covered by a blanket project MIT grant. Do not copy those artifacts into a release without carrying their recorded licenses and reviewing their contents.

## Apache License, Version 2.0

The complete, unmodified Apache-2.0 license text from the pinned ZXing-C++ source archive follows. It is included for the Apache-licensed materials identified above; it does not relicense the other listed materials.

```text
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "{}"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright {yyyy} {name of copyright owner}

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
